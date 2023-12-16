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
    msg = msg.encode()
    return b''.join((msg_type.to_bytes(1), len(msg).to_bytes(4), msg))

def decode_header(header: bytes) -> tuple[int, int]:
    return (int.from_bytes(header[:1]), int.from_bytes(header[1:]))

class PlayerType(IntEnum):
    LORD = auto()
    FARMER = auto()
    SPECTATOR = auto()
