from notification.notification_service import NotificationService

import json
import requests


class SlackNotificationService(NotificationService):
    slack_id: str

    def __init__(self, slack_id: str):
        self.slack_id = slack_id

    def notify(self, message, options=None):
        if self.slack_id is None:
            print("Slack notifications are not configured, disabling Slack notifications...")
            pass

        slack_url = "https://hooks.slack.com/services/{}".format(self.slack_id)
        slack_data = {'text': message}

        response = requests.post(
            slack_url,
            data=json.dumps(slack_data),
            headers={'Content-Type': 'application/json'}
        )

        if response.status_code != 200:
            raise ValueError('Request to Slack returned an error {}, the response is:\n{}'
                             .format(response.status_code, response.text))
