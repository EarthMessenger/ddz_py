import argparse
import asyncio
import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.patch_stdout import patch_stdout

from .client import DdzClient
from .protocol import *

class DdzClientDeluxe:
    def __init__(self, hostname: str, port: int, name: str):
        self.client = DdzClient(hostname, port, name)

    def receive_message_cb(self, data):
        if data['type'] == 'tell':
            for s in data['content'].splitlines():
                print(f'[server] {s}')
        elif data['type'] == 'chat':
            author = data['author']
            for s in data['content'].splitlines():
                print(f'{author}> {s}')
        elif data['type'] == 'play':
            print(data['player'], data['cards'])
        elif data['type'] == 'rating_update':
            print('k = ', data['k'])
            for d in data['delta']:
                print(d['name'], d['delta'], d['rating'], sep = '\t')
        elif data['type'] == 'error':
            print(f'[error] {data["what"]}')
        elif data['type'] == 'sync':
            for change in data['attr']:
                k, v = change['key'], change['val']
                if k == 'player_type':
                    print(f'You are {v} now')
                elif k == 'cards':
                    print(''.join(v))
                elif k == 'always_spectator':
                    if v:
                        print('You are an always spectator now.')
                    else:
                        print('You are a normal player now.')
        elif data['type'] == 'start':
            for i in data['players']:
                print(i['name'], i['role'], sep = '\t')
        else:
            print(data)

    async def receive_input(self):
        cmd_completer = WordCompleter([
            '/start', '/start4', '/list', '/rating', '/remain', '/toggle_spectator', '/undo'])
        session = PromptSession(completer=cmd_completer)
        while True:
            try:
                msg = await session.prompt_async()
                await self.client.handle_input(msg)
            except (EOFError, KeyboardInterrupt):
                break
            except Exception as e:
                print(e)

    async def run(self):
        await self.client.connect()
        with patch_stdout(True):
            try:
                receive_task = asyncio.create_task(self.client.receive_message(self.receive_message_cb))
                await self.receive_input()
            finally:
                receive_task.cancel()
                await self.client.close_writer()


if __name__== '__main__':
    parser = argparse.ArgumentParser(
            description='deluxe client of ddz_py')
    parser.add_argument('hostname', help='the hostname of the ddz_py server')
    parser.add_argument('port', help='the port of the ddz_py server', type=int)
    parser.add_argument('name', help='your username')

    args = parser.parse_args()

    client = DdzClientDeluxe(args.hostname, args.port, args.name)
    asyncio.run(client.run())
