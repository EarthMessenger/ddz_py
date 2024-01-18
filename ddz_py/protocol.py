from enum import IntEnum, auto

# | body length | body (json) |
# |      4B     |             |

class ClientMsgType(IntEnum):
    JOIN = auto()
    CHAT = auto()
    PLAY = auto()
    CMD = auto()

class ServerMsgType(IntEnum):
    DEAL = auto()
    MSG = auto()

def encode_msg(msg: str) -> bytes:
    bmsg = msg.encode()
    return b''.join((len(bmsg).to_bytes(4, byteorder='big'), bmsg))

def decode_header(header: bytes) -> tuple[int, int]:
    return (int.from_bytes(header[:1], byteorder='big'), int.from_bytes(header[1:], byteorder='big'))

class PlayerType(IntEnum):
    LORD = auto()
    FARMER = auto()
    SPECTATOR = auto()

def get_player_from_card_cnt(card_cnt: int) -> PlayerType:
    if card_cnt == 0:
        return PlayerType.SPECTATOR
    elif card_cnt == 17 or card_cnt == 25:
        return PlayerType.FARMER
    elif card_cnt == 20 or card_cnt == 33:
        return PlayerType.LORD
    else:
        raise ValueError('unknown player type')

def get_player_type_name(p: PlayerType) -> str:
    if p == PlayerType.LORD:
        return 'lord'
    elif p == PlayerType.FARMER:
        return 'farmer'
    elif p == PlayerType.SPECTATOR:
        return 'spectator'
    else:
        raise ValueError('unknown player type')
