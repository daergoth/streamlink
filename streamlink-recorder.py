# This script checks if a user on twitch is currently streaming and then records the stream via streamlink
import subprocess
import pycountry
import argparse
import random
import string
import shutil
import time
import os

from threading import Timer
from datetime import datetime

from notification.notification_service_repository import NotificationServiceRepository
from notification.implementations.slack_notification_service import SlackNotificationService

## enable extra logging
# import logging
# import sys
# log = logging.getLogger('requests_oauthlib')
# log.addHandler(logging.StreamHandler(sys.stdout))
# log.setLevel(logging.DEBUG)

# Constants
from twitch.stream_check import StreamCheck
from twitch.stream_check_service import TwitchStreamCheckService

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

stream_check_service = None


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
    NotificationServiceRepository.get_instance().notify_start_recording(username, stream_title)
    print(user, "recording ... ")

    start_streamlink(recorded_filename)
    add_metadata(recorded_filename, stream_title, language)

    NotificationServiceRepository.get_instance().notify_end_recording(username, stream_title)
    print("Stream is done. Going back to checking.. ")


def loopcheck(do_delete):
    info = stream_check_service.check_user(user)
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
        # Wait for problematic stream parts to pass
        time.sleep(10)
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

    global stream_check_service

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

    NotificationServiceRepository.get_instance().register_notification_service(SlackNotificationService(slack_id))
    stream_check_service = TwitchStreamCheckService(client_id, client_secret, game_list.split(","))

    print("Checking for", user, "every", timer, "seconds. Record with", quality, "quality.")
    loopcheck(True)


if __name__ == "__main__":
    # execute only if run as a script
    main()
