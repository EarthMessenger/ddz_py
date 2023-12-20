import argparse
import asyncio
import sys

from .protocol import *
from .card import *

# from https://stackoverflow.com/a/65326191/18180934
async def ainput():
    return (await asyncio.get_event_loop().run_in_executor(
            None, sys.stdin.readline))

class DdzClient:
    def __init__(self, hostname: str, port: int, name: str):
        self.hostname = hostname
        self.port = port
        self.name = name
        self.cards: list[str] = []
        self.player_type = PlayerType.SPECTATOR

    async def connect(self):
        self.reader, self.writer = await asyncio.open_connection(
                self.hostname, self.port)
        await self.join()

    async def join(self):
        self.writer.write(encode_msg(ClientMsgType.JOIN, self.name))
        await self.writer.drain()

    async def close_writer(self):
        self.writer.close()
        await self.writer.wait_closed()

    def check_have_cards(self, cards: str) -> bool:
        old_cards = self.cards.copy()
        for c in cards:
            if not c in old_cards:
                return False
            old_cards.remove(c)
        return True

    def remove_cards(self, cards: str):
        for c in cards:
            self.cards.remove(c)

    def add_cards(self, cards: str):
        for c in cards:
            for d in c:
                self.cards.append(d)
        self.sort_cards()

    def sort_cards(self):
        self.cards.sort(key = lambda x : card_rank[x])

    def show_cards(self):
        if len(self.cards):
            print(f'{"".join(self.cards)} ({len(self.cards)})')
        else:
            print('you don\'t have any card.')

    async def handle_cmd(self, cmd: str):
        cmds = cmd.split()
        if len(cmds) == 0:
            return
        if cmds[0] == 'add':
            if len(cmds) != 2:
                raise Exception('usage: /add <cards>')
            self.add_cards(cmds[1])
            await self.send_msg(encode_msg(ClientMsgType.CMD, cmd))
        elif cmds[0] == 'start':
            await self.send_msg(encode_msg(ClientMsgType.CMD, cmd))
        elif cmds[0] == 'show':
            self.show_cards()
        elif cmds[0] == 'list':
            await self.send_msg(encode_msg(ClientMsgType.CMD, cmd))
        else:
            raise Exception('unknown commands, use /help to list available commands')

    async def handle_play(self, cards: str):
        if self.player_type == PlayerType.SPECTATOR:
            await self.handle_chat(cards)
            return
        cards = cards.upper()
        if not self.check_have_cards(cards):
            raise Exception('you don\'t have these card(s)')
        self.remove_cards(cards)
        print(f'{"".join(self.cards)} ({len(self.cards)})')
        await self.send_msg(encode_msg(ClientMsgType.PLAY, cards))

    async def handle_chat(self, msg: str):
        await self.send_msg(encode_msg(ClientMsgType.CHAT, msg))

    async def send_msg(self, msg: bytes):
        self.writer.write(msg)
        await self.writer.drain()

    async def handle_input(self):
        while True:
            msg = await ainput()
            if not msg:
                break
            msg = msg.rstrip('\n')
            try:
                if len(msg) == 0: # PASS
                    await self.handle_play('')
                elif msg[0] == '!':
                    await self.handle_chat(msg[1:].strip())
                elif msg[0] == '/':
                    await self.handle_cmd(msg[1:].strip())
                else:
                    await self.handle_play(msg.strip())
            except Exception as e:
                print(e)
        await self.close_writer()

    async def receive_message(self):
        while True:
            try: 
                header = await self.reader.readexactly(5)
                msg_type, msg_length = decode_header(header)
                body = (await self.reader.readexactly(msg_length)).decode()
            except:
                break
            if msg_type == ServerMsgType.DEAL:
                self.cards = list(body)
                self.sort_cards()
                self.player_type = get_player_from_card_cnt(len(self.cards))
                print(f'you are {get_player_type_name(self.player_type)}')
                self.show_cards()
            elif msg_type == ServerMsgType.MSG:
                print(body)
        await self.close_writer()

    async def run(self):
        await self.connect()
        await asyncio.gather(
                self.handle_input(),
                self.receive_message())

if __name__== '__main__':
    parser = argparse.ArgumentParser(
            description='client of ddz_py')
    parser.add_argument('hostname', help='the hostname of the ddz_py server')
    parser.add_argument('port', help='the port of the ddz_py server', type=int)
    parser.add_argument('name', help='your username')

    args = parser.parse_args()

    client = DdzClient(args.hostname, args.port, args.name)
    asyncio.run(client.run())
