from typing import List

from twitch.stream_check import StreamCheck
from twitch.twitch_service import TwitchService

GameIdList = List[str]


class TwitchStreamCheckService(TwitchService):

    whitelisted_games: GameIdList

    def __init__(self, client_id, client_secret, whitelisted_games):
        super().__init__(client_id, client_secret)
        self.whitelisted_games = whitelisted_games

    def check_user(self, streamer_username):
        data = None
        try:
            info = self.get_from_twitch('streams?user_login=' + streamer_username)

            if len(info['data']) == 0:
                status = StreamCheck.OFFLINE
            else:
                data = info['data'][0]
                if len(self.whitelisted_games) > 0 and info['data'][0].get("game_id") not in self.whitelisted_games:
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
