import asyncio
import json
import sys

from .protocol import *
from .card import *
from .data import DdzPlayer

class DdzClient:
    def __init__(self, hostname: str, port: int, name: str):
        self.hostname = hostname
        self.port = port
        self.data = DdzPlayer(name)

    async def connect(self):
        self.reader, self.writer = await asyncio.open_connection(
                self.hostname, self.port)
        await self.send(json.dumps({
            'type': 'join',
            'name': self.data.name}))

    async def send(self, msg: str):
        bmsg = encode_msg(msg)
        self.writer.write(bmsg)
        await self.writer.drain()

    async def close_writer(self):
        self.writer.close()
        await self.writer.wait_closed()

    async def handle_cmd(self, cmd: str):
        await self.send(json.dumps({
            'type': 'cmd',
            'cmd': cmd}))

    async def handle_play(self, cards: str):
        cards = cards.upper()
        if not self.data.check_have_cards(list(cards)):
            raise Exception('you don\'t have these card(s)')
        await self.send(json.dumps({
            'type': 'play',
            'cards': cards}))

    async def handle_chat(self, msg: str):
        await self.send(json.dumps({
            'type': 'chat',
            'content': msg}))

    async def handle_input(self, msg: str):
        if msg.startswith('!'):
            await self.handle_chat(msg[1:].strip())
        elif msg.startswith('/'):
            await self.handle_cmd(msg[1:].strip())
        elif not self.data.player_type.startswith('spectator'): # spectator cannot play cards
            await self.handle_play(msg.strip())
        else:
            await self.handle_chat(msg.strip())

    async def receive_message(self, cb):
        while True:
            try: 
                length = int.from_bytes(await self.reader.readexactly(4), byteorder = 'big')
                body = json.loads(await self.reader.readexactly(length))
            except Exception as e:
                print(e)
                break
            if body['type'] == 'sync':
                for change in body['attr']:
                    k, v = change['key'], change['val']
                    if k == 'cards':
                        if len(v) != len(self.data.cards):
                            if len(v) == 1:
                                await self.handle_chat(f'Only 1 card!')
                            elif len(v) == 2:
                                await self.handle_chat(f'Only 2 cards!')
                    setattr(self.data, change['key'], change['val'])
            cb(body)
        await self.close_writer()
