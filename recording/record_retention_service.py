import os
import time

from recording.recording_constants import SAVE_PATH


class RecordRetentionService:
    recording_retention_period_in_days: int
    recording_size_limit_in_mb: int

    def __init__(self, time_limit: int, size_limit: int):
        self.recording_retention_period_in_days = time_limit
        self.recording_size_limit_in_mb = size_limit

    def check_recording_limits(self):
        print("Checking for recordings to delete...")

        files = [os.path.join(SAVE_PATH, f) for f in os.listdir(SAVE_PATH)]
        augmented_files = [
            {"filename": f, "size": os.stat(f).st_size, "mod_time": os.stat(f).st_mtime, "deleted": False}
            for f in files
        ]
        augmented_files = sorted(augmented_files, key=lambda f: f["mod_time"], reverse=True)

        augmented_files = self.__check_time_limit(augmented_files)

        augmented_files = self.__check_size_limit(augmented_files)

        return augmented_files

    def __check_time_limit(self, files):
        if self.recording_retention_period_in_days > 0:
            current_day_limit = int(time.time()) - (self.recording_retention_period_in_days * 24 * 60 * 60)
            for f in files:
                if f["mod_time"] < current_day_limit:
                    print("Too old recording, deleting {}... ".format(f["filename"]))
                    os.remove(f["filename"])
                    f["deleted"] = True

        return [f for f in files if not f["deleted"]]

    def __check_size_limit(self, files):
        if self.recording_size_limit_in_mb > 0:
            sum_size = 0
            for f in files:
                if sum_size > self.recording_size_limit_in_mb:
                    print("Recordings exceeding size limit, deleting {}...".format(f["filename"]))
                    os.remove(f["filename"])
                    f["deleted"] = True
                sum_size += (f["size"] / 1024 / 1024)

        return [f for f in files if not f["deleted"]]
