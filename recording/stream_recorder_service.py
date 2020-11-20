import os
import random
import shutil
import string
import subprocess
from datetime import datetime

import pycountry

from recording.record_retention_service import RecordRetentionService
from recording.recording_constants import SAVE_PATH
from notification.notification_service_repository import NotificationServiceRepository


class StreamRecorderService:
    record_retention_service: RecordRetentionService

    def __init__(self, record_retention_service: RecordRetentionService):
        self.record_retention_service = record_retention_service

    def start_recording(self, stream_data, quality="best", do_delete=True, streamlink_args=""):
        if do_delete:
            self.record_retention_service.check_recording_limits()
        self.__record_stream(stream_data, quality, streamlink_args)

    def __record_stream(self, stream_data, quality, streamlink_args):
        stream_title = stream_data["title"]
        username = stream_data["user_name"]
        language = stream_data["language"]

        filename = stream_title + " - " + username + " - " + datetime.now().strftime("%Y-%m-%d %H-%M-%S") + ".mp4"
        # clean filename from invalid characters
        filename = "".join(x for x in filename if x not in ["\\", "/", ":", "*", "?", "\"", "<", ">", "|"])
        recorded_filename = os.path.join(SAVE_PATH, filename)

        # start streamlink process
        NotificationServiceRepository.get_instance().notify_start_recording(username, stream_title)
        print(username, "recording ... ")

        self.__start_streamlink(recorded_filename, username, quality, streamlink_args)
        if os.path.exists(recorded_filename):
            self.__add_metadata(recorded_filename, stream_title, language)

        NotificationServiceRepository.get_instance().notify_end_recording(username, stream_title)
        print("Stream is done. Going back to checking.. ")

    def __start_streamlink(self, recorded_filename, user, quality, streamlink_args):
        recorded_filename = "\"" + recorded_filename + "\""

        arguments = ["streamlink",
                     "--twitch-disable-hosting", "--twitch-disable-ads", "--twitch-disable-reruns",
                     "--hls-live-restart", "--retry-max", "5", "--retry-streams", "60",
                     "twitch.tv/" + user, quality,
                     "-o", recorded_filename,
                     streamlink_args]
        return subprocess.call(" ".join(arguments), shell=True)

    def __get_tmp_filename(self, length):
        letters_and_digits = string.ascii_letters + string.digits
        return ''.join((random.choice(letters_and_digits) for i in range(length)))

    def __add_metadata(self, recorded_filename, title, language):
        tmp_filename = os.path.join("/tmp/", self.__get_tmp_filename(32) + ".mp4")
        lang = pycountry.languages.get(alpha_2=language)

        arguments = ["ffmpeg",
                     "-i", "\"" + recorded_filename + "\"",
                     "-metadata", "title=\"{}\"".format(title),
                     "-metadata:s:a:0", "language={}".format(lang.alpha_3),
                     "-codec", "copy",
                     tmp_filename]
        subprocess.call(" ".join(arguments), shell=True)
        result = shutil.copy2(tmp_filename, recorded_filename)
        os.remove(tmp_filename)
        return result
