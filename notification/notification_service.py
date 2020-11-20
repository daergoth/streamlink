
class NotificationService:

    def notify(self, message, options=None):
        pass

    def notify_start_recording(self, streamer_name, stream_title):
        msg = "Started recording {}: {}...".format(streamer_name, stream_title)
        self.notify(msg)

    def notify_end_recording(self, streamer_name, stream_title):
        msg = "Ended recording {}: {}...".format(streamer_name, stream_title)
        self.notify(msg)
