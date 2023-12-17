import argparse
import asyncio
import sys

from ddz_py.protocol import *
from ddz_py.card import *

# from https://stackoverflow.com/a/65326191/18180934
async def ainput():
    return (await asyncio.get_event_loop().run_in_executor(
            None, sys.stdin.readline))

class DdzClient:
    def __init__(self, hostname: str, port: int, name: str):
        self.hostname = hostname
        self.port = port
        self.name = name
        self.cards = []

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

    def check_have_card(self, cards: str) -> bool:
        old_cards = self.cards.copy()
        for c in cards:
            if not c in old_cards:
                return False
            old_cards.remove(c)
        return True

    def remove_card(self, cards: str):
        for c in cards:
            self.cards.remove(c)

    def add_cards(self, cards: str):
        for c in cards:
            self.cards.append(c)
        self.sort_cards()

    def sort_cards(self):
        self.cards.sort(key = lambda x : card_rank[x])

    def exec_command(self, cmd: str):
        cmd = cmd.split()
        if len(cmd) == 0:
            return
        if cmd[0] == 'add':
            self.add_cards(cmd[1])

    def print_cards(self):
        if len(self.cards):
            print(''.join(self.cards))

    async def handle_input(self):
        while True:
            msg = await ainput()
            if not msg:
                break
            msg = msg.rstrip('\n')
            if len(msg) == 0: # PASS
                msg_type = ClientMsgType.PLAY
            if msg[0] == '!':
                msg_type = ClientMsgType.CHAT
                msg = msg[1:].strip()
            elif msg[0] == '/':
                msg_type = ClientMsgType.CMD
                msg = msg[1:]
                self.exec_command(msg)
            else:
                msg_type = ClientMsgType.PLAY
                msg = msg.upper()
                if not self.check_have_card(msg):
                    print('You dont have these cards')
                    continue
                self.remove_card(msg)
                self.print_cards()
            self.writer.write(encode_msg(msg_type, msg))
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
                print(f'now you are {get_player_type_str(len(self.cards))}')
                self.print_cards()
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
