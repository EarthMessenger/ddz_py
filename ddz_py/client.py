import asyncio
import sys

from .protocol import *
from .card import *

class DdzClientData:
    def __init__(self, name: str):
        self.name = name
        self.cards: list[str] = []
        self.player_type = PlayerType.SPECTATOR

    def check_have_cards(self, cards: str) -> bool:
        old_cards = self.cards.copy()
        for c in cards:
            if not c in old_cards:
                return False
            old_cards.remove(c)
        return True

    def sort_cards(self):
        self.cards.sort(key = lambda x : card_rank[x])

    def add_cards(self, cards: list[str]):
        for c in cards:
            self.cards.append(c)
        self.sort_cards()

    def remove_cards(self, cards: str):
        for c in cards:
            self.cards.remove(c)

    def set_cards(self, cards: str):
        self.cards = list(cards)
        self.sort_cards()

class DdzClient:
    def __init__(self, hostname: str, port: int, name: str):
        self.hostname = hostname
        self.port = port
        self.data = DdzClientData(name)

    async def connect(self):
        self.reader, self.writer = await asyncio.open_connection(
                self.hostname, self.port)
        await self.join()

    async def join(self):
        self.writer.write(encode_msg(ClientMsgType.JOIN, self.data.name))
        await self.writer.drain()

    async def close_writer(self):
        self.writer.close()
        await self.writer.wait_closed()

    async def handle_cmd(self, cmd: str):
        await self.send_msg(encode_msg(ClientMsgType.CMD, cmd))

    async def handle_play(self, cards: str):
        cards = cards.upper()
        if not self.data.check_have_cards(cards):
            raise Exception('you don\'t have these card(s)')
        self.data.remove_cards(cards)
        await self.send_msg(encode_msg(ClientMsgType.PLAY, cards))

    async def handle_chat(self, msg: str):
        await self.send_msg(encode_msg(ClientMsgType.CHAT, msg))

    async def send_msg(self, msg: bytes):
        self.writer.write(msg)
        await self.writer.drain()

    async def handle_input(self, msg: str):
        if msg.startswith('!'):
            await self.handle_chat(msg[1:].strip())
        elif msg.startswith('/'):
            await self.handle_cmd(msg[1:].strip())
        else:
            await self.handle_play(msg.strip())

    async def receive_message(self, cb):
        while True:
            try: 
                header = await self.reader.readexactly(5)
                msg_type, msg_length = decode_header(header)
                body = (await self.reader.readexactly(msg_length)).decode()
            except:
                break
            if msg_type == ServerMsgType.DEAL:
                self.data.set_cards(body)
                self.data.player_type = get_player_from_card_cnt(len(self.data.cards))
            cb(msg_type, body)
        await self.close_writer()
