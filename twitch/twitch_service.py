import json

from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import BackendApplicationClient


class TwitchService:

    client_id: str
    client_secret: str

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret

    def get_from_twitch(self, operation):
        client = BackendApplicationClient(client_id=self.client_id)
        oauth = OAuth2Session(client=client)
        token = oauth.fetch_token(token_url='https://id.twitch.tv/oauth2/token', client_id=self.client_id,
                                  client_secret=self.client_secret, include_client_id=True)

        url = 'https://api.twitch.tv/helix/' + operation
        response = oauth.get(url, headers={'Accept': 'application/json', 'Client-ID': self.client_id})

        info = None
        if response.status_code != 200:
            raise ValueError('Request to twitch returned an error {}, the response is:\n{}'
                             .format(response.status_code, response.text))
        try:
            info = json.loads(response.content)
            # print(json.dumps(info, indent=4, sort_keys=True))
        except Exception as e:
            print(e)

        return info
