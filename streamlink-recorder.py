# This script checks if a user on twitch is currently streaming and then records the stream via streamlink
import subprocess
import pycountry
import argparse
import requests
import random
import string
import shutil
import json
import time
import os

from enum import Enum
from threading import Timer
from datetime import datetime
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session

## enable extra logging
# import logging
# import sys
# log = logging.getLogger('requests_oauthlib')
# log.addHandler(logging.StreamHandler(sys.stdout))
# log.setLevel(logging.DEBUG)

# Constants
SAVE_PATH = "/download/"

# Init variables with some default values
timer = 30
user = ""
quality = "best"
client_id = ""
client_secret = ""
token = ""
slack_id = ""
game_list = ""
streamlink_args = ""
recording_size_limit_in_mb = "0"
recording_retention_period_in_days = "3"


# Init variables with some default values
def post_to_slack(message):
    if slack_id is None:
        print("slackid is not specified, so disabling slack notification")
        pass

    slack_url = "https://hooks.slack.com/services/" + slack_id
    slack_data = {'text': message}

    response = requests.post(
        slack_url, data=json.dumps(slack_data),
        headers={'Content-Type': 'application/json'}
    )
    if response.status_code != 200:
        raise ValueError(
            'Request to slack returned an error %s, the response is:\n%s'
            % (response.status_code, response.text)
        )


# still need to manage token refresh based on expiration
def get_from_twitch(operation):
    client = BackendApplicationClient(client_id=client_id)
    oauth = OAuth2Session(client=client)
    token = oauth.fetch_token(token_url='https://id.twitch.tv/oauth2/token', client_id=client_id, client_secret=client_secret,include_client_id=True)

    url = 'https://api.twitch.tv/helix/' + operation
    response = oauth.get(url, headers={'Accept': 'application/json', 'Client-ID': client_id})

    if response.status_code != 200:
        raise ValueError(
            'Request to twitch returned an error %s, the response is:\n%s'
            % (response.status_code, response.text)
        )
    try:
        info = json.loads(response.content)
        # print(json.dumps(info, indent=4, sort_keys=True))
    except Exception as e:
        print(e)
    return info


class StreamCheck(Enum):
    ONLINE = 0
    OFFLINE = 1
    USER_NOT_FOUND = 2
    ERROR = 3
    UNWANTED_GAME = 4


def check_user(streamer_username):
    data = None
    try:
        info = get_from_twitch('streams?user_login=' + streamer_username)
        if len(info['data']) == 0:
            status = StreamCheck.OFFLINE
        elif game_list != '' and info['data'][0].get("game_id") not in game_list.split(','):
            status = StreamCheck.UNWANTED_GAME
            data = info['data'][0]
        else:
            status = StreamCheck.ONLINE
            data = info['data'][0]
    except Exception as e:
        print(e)
        status = StreamCheck.ERROR
    return {
        "status": status,
        "data": data
    }


def check_recording_limits():
    print("Checking for recordings to delete...")

    files = [os.path.join(SAVE_PATH, f) for f in os.listdir(SAVE_PATH)]
    augmented_files = [
        {"filename": f, "size": os.stat(f).st_size, "mod_time": os.stat(f).st_mtime, "deleted": False}
        for f in files
    ]
    augmented_files = sorted(augmented_files, key=lambda f: f["mod_time"], reverse=True)
    current_epoch_time = int(time.time())

    if recording_retention_period_in_days is not None and recording_retention_period_in_days != "":
        day_limit = int(recording_retention_period_in_days)
        if day_limit > 0:
            current_day_limit = current_epoch_time - (day_limit * 24 * 60 * 60)
            for f in augmented_files:
                if f["mod_time"] < current_day_limit:
                    print("Too old recording, deleting {}... ".format(f["filename"]))
                    os.remove(f["filename"])
                    f["deleted"] = True

    augmented_files = [f for f in augmented_files if not f["deleted"]]

    if recording_size_limit_in_mb is not None and recording_size_limit_in_mb != "":
        size_limit = int(recording_size_limit_in_mb)
        if size_limit > 0:
            sum_size = augmented_files[0]["size"]
            for f in augmented_files[1:]:
                sum_size += (f["size"] / 1024 / 1024)
                if sum_size > size_limit:
                    print("Recordings exceeding size limit, deleting {}...".format(f["filename"]))
                    os.remove(f["filename"])


def start_streamlink(recorded_filename):
    recorded_filename = "\"" + recorded_filename + "\""

    post_to_slack("recording " + user + " ...")
    print(user, "recording ... ")

    arguments = ["streamlink",
                 "--twitch-disable-hosting", "--twitch-disable-ads", "--twitch-disable-reruns",
                 "--hls-live-restart", "--retry-max", "5", "--retry-streams", "60",
                 "twitch.tv/" + user, quality,
                 "-o", recorded_filename,
                 streamlink_args]
    return subprocess.call(" ".join(arguments), shell=True)


def get_tmp_filename(length):
    letters_and_digits = string.ascii_letters + string.digits
    return ''.join((random.choice(letters_and_digits) for i in range(length)))


def add_metadata(recorded_filename, title, language):
    tmp_filename = os.path.join("/tmp/", get_tmp_filename(32) + ".mp4")
    lang = pycountry.languages.get(alpha_2=language)

    arguments = ["ffmpeg",
                 "-i", "\"" + recorded_filename + "\"",
                 "-metadata", "title=\"{}\"".format(title),
                 "-metadata:s:a:0", "language={}".format(lang.alpha_3),
                 "-codec", "copy",
                 tmp_filename]
    subprocess.call(" ".join(arguments), shell=True)
    return shutil.copy2(tmp_filename, recorded_filename)


def record_stream(stream_data):
    stream_title = stream_data["title"]
    username = stream_data["user_name"]
    language = stream_data["language"]

    filename = stream_title + " - " + username + " - " + datetime.now().strftime("%Y-%m-%d %H-%M-%S") + ".mp4"
    # clean filename from invalid characters
    filename = "".join(x for x in filename if x not in ["\\", "/", ":", "*", "?", "\"", "<", ">", "|"])
    recorded_filename = os.path.join(SAVE_PATH, filename)

    # start streamlink process
    start_streamlink(recorded_filename)
    add_metadata(recorded_filename, stream_title, language)

    print("Stream is done. Going back to checking.. ")
    post_to_slack("Stream " + user + " is done. Going back to checking..")


def loopcheck(do_delete):
    info = check_user(user)
    status = info["status"]
    stream_data = info["data"]

    if status == StreamCheck.USER_NOT_FOUND:
        print("username not found. invalid username?")
        return
    elif status == StreamCheck.ERROR:
        print("unexpected error. maybe try again later")
    elif status == StreamCheck.OFFLINE:
        print(user, "currently offline, checking again in", timer, "seconds")
    elif status == StreamCheck.UNWANTED_GAME:
        print("unwanted game stream, checking again in", timer, "seconds")
    elif status == StreamCheck.ONLINE:
        if do_delete:
            check_recording_limits()
        record_stream(stream_data)
        loopcheck(False)

    t = Timer(timer, loopcheck, [True])
    t.start()


def main():
    global timer
    global user
    global quality
    global client_id
    global client_secret
    global slack_id
    global game_list
    global streamlink_args
    global recording_size_limit_in_mb
    global recording_retention_period_in_days

    parser = argparse.ArgumentParser()
    parser.add_argument("-timer", help="Stream check interval (less than 15s are not recommended)")
    parser.add_argument("-user", help="Twitch user that we are checking")
    parser.add_argument("-quality", help="Recording quality")
    parser.add_argument("-clientid", help="Your twitch app client id")
    parser.add_argument("-clientsecret", help="Your twitch app client secret")
    parser.add_argument("-slackid", help="Your slack app client id")
    parser.add_argument("-gamelist", help="The game list to be recorded")
    parser.add_argument("-streamlinkargs", help="Additional arguments for streamlink")
    parser.add_argument("-recordingsizelimit", help="Older recordings will be deleted so the remaining will take up space upto the given limit in MBs")
    parser.add_argument("-recordingretention", help="Recording older than the given limit (in days) will be deleted")
    args = parser.parse_args()
 
    if args.timer is not None:
        timer = int(args.timer)
    if args.user is not None:
        user = args.user
    if args.quality is not None:
        quality = args.quality
    if args.slackid is not None:
        slack_id = args.slackid
    if args.gamelist is not None:
        game_list = args.gamelist

    if args.clientid is not None:
        client_id = args.clientid
    if args.clientsecret is not None:
        client_secret = args.clientsecret
    if client_id is None:
        print("Please create a twitch app and set the client id with -clientid [YOUR ID]")
        return
    if client_secret is None:
        print("Please create a twitch app and set the client secret with -clientsecret [YOUR SECRET]")
        return

    if args.streamlinkargs is not None:
        streamlink_args = args.streamlinkargs
    if args.recordingsizelimit is not None:
        recording_size_limit_in_mb = args.recordingsizelimit
    if args.recordingretention is not None:
        recording_retention_period_in_days = args.recordingretention

    print("Checking for", user, "every", timer, "seconds. Record with", quality, "quality.")
    loopcheck(True)


if __name__ == "__main__":
    # execute only if run as a script
    main()
