import argparse
import time

from threading import Timer

from twitch.stream_check import StreamCheck
from twitch.stream_check_service import TwitchStreamCheckService
from recording.stream_recorder_service import StreamRecorderService
from recording.record_retention_service import RecordRetentionService
from notification.notification_service_repository import NotificationServiceRepository
from notification.implementations.slack_notification_service import SlackNotificationService

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
game_list = []
streamlink_args = ""
recording_size_limit_in_mb = 0
recording_retention_period_in_days = 3

# Services
stream_check_service: TwitchStreamCheckService = None
stream_recorder_service: StreamRecorderService = None
record_retention_service: RecordRetentionService = None


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
        stream_recorder_service.start_recording(
            stream_data,
            quality=quality,
            do_delete=do_delete,
            streamlink_args=streamlink_args)

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
    global stream_recorder_service
    global record_retention_service

    parser = argparse.ArgumentParser()
    parser.add_argument("-timer",
                        help="Stream check interval (less than 15s are not recommended)")
    parser.add_argument("-user",
                        help="Twitch user that we are checking")
    parser.add_argument("-quality",
                        help="Recording quality")
    parser.add_argument("-gamelist",
                        help="The game list to be recorded")

    parser.add_argument("-clientid",
                        help="Your twitch app client id")
    parser.add_argument("-clientsecret",
                        help="Your twitch app client secret")

    parser.add_argument("-slackid",
                        help="Your slack app client id")

    parser.add_argument("-streamlinkargs",
                        help="Additional arguments for streamlink")

    parser.add_argument("-recordingsizelimit",
                        default="0",
                        help="Older recordings will be deleted so the remaining will take up space upto the given limit in MBs")
    parser.add_argument("-recordingretention",
                        default="0",
                        help="Recording older than the given limit (in days) will be deleted")
    args = parser.parse_args()
 
    if args.timer is not None and args.timer != "":
        timer = int(args.timer)
    if args.user is not None:
        user = args.user
    if args.quality is not None:
        quality = args.quality
    if args.slackid is not None:
        slack_id = args.slackid
    if args.gamelist is not None and args.gamelist != "":
        game_list = args.gamelist.split(",")

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
    if args.recordingsizelimit is not None and args.recordingsizelimit != "":
        recording_size_limit_in_mb = int(args.recordingsizelimit)
    if args.recordingretention is not None and args.recordingretention != "":
        recording_retention_period_in_days = int(args.recordingretention)

    NotificationServiceRepository.get_instance().register_notification_service(SlackNotificationService(slack_id))

    record_retention_service = RecordRetentionService(recording_retention_period_in_days, recording_size_limit_in_mb)

    stream_recorder_service = StreamRecorderService(record_retention_service)
    stream_check_service = TwitchStreamCheckService(client_id, client_secret, game_list)

    print("Checking for", user, "every", timer, "seconds. Record with", quality, "quality.")
    loopcheck(True)


if __name__ == "__main__":
    # execute only if run as a script
    main()
