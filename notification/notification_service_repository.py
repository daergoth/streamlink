from typing import List

from notification.notification_service import NotificationService

NotificationServiceList = List[NotificationService]


class NotificationServiceRepository(NotificationService):
    __instance = None
    notification_service_list: NotificationServiceList = []

    @staticmethod
    def get_instance():
        if NotificationServiceRepository.__instance is None:
            NotificationServiceRepository()
        return NotificationServiceRepository.__instance

    def __init__(self):
        if NotificationServiceRepository.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            NotificationServiceRepository.__instance = self

    def notify(self, message, options=None):
        print("Notifying on every configured channel...")
        for svc in self.notification_service_list:
            svc.notify(message, options)

    def register_notification_service(self, notification_service: NotificationService):
        self.notification_service_list.append(notification_service)

    def unregister_notification_service(self, notification_service: NotificationService):
        self.notification_service_list.remove(notification_service)
