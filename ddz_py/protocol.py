from enum import IntEnum, auto

# | msg type | body length | body |
# |    1B    |      4B     |      |
# |       header           |      |

class ClientMsgType(IntEnum):
    JOIN = auto()
    CHAT = auto()
    PLAY = auto()
    CMD = auto()

class ServerMsgType(IntEnum):
    DEAL = auto()
    MSG = auto()

def encode_msg(msg_type: int, msg: str) -> bytes:
    bmsg = msg.encode()
    return b''.join((msg_type.to_bytes(1, byteorder='big'), len(bmsg).to_bytes(4, byteorder='big'), bmsg))

def decode_header(header: bytes) -> tuple[int, int]:
    return (int.from_bytes(header[:1], byteorder='big'), int.from_bytes(header[1:], byteorder='big'))

class PlayerType(IntEnum):
    LORD = auto()
    FARMER = auto()
    SPECTATOR = auto()

def get_player_type_str(card_cnt: int) -> str:
    if card_cnt == 0:
        return 'spectator'
    elif card_cnt == 17:
        return 'farmer'
    elif card_cnt == 20:
        return 'lord'
    else:
        raise Exception('invalid card count')
