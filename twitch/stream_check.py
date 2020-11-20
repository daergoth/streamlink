from enum import Enum


class StreamCheck(Enum):
    ONLINE = 0
    OFFLINE = 1
    USER_NOT_FOUND = 2
    ERROR = 3
    UNWANTED_GAME = 4
