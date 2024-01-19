import argparse
import asyncio
import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.patch_stdout import patch_stdout

from colorama import just_fix_windows_console, Fore, Back, Style

from .client import DdzClient
from .protocol import *

def get_color_from_role(role: str) -> str:
    if role.startswith('landlord'):
        return Fore.CYAN + Style.BRIGHT
    elif role.startswith('peasant'):
        return Fore.YELLOW + Style.BRIGHT
    else:
        return ''

class DdzClientDeluxe:
    def __init__(self, hostname: str, port: int, name: str):
        self.client = DdzClient(hostname, port, name)
        self.player_roles: dict[str, str] = dict()

    def get_role(self, name: str):
        if name in self.player_roles:
            return self.player_roles[name]
        else:
            return 'spectator'

    def color_player(self, name: str):
        return get_color_from_role(self.get_role(name)) + name + Style.RESET_ALL

    def receive_message_cb(self, data):
        if data['type'] == 'tell':
            for s in data['content'].splitlines():
                print(f'{Fore.BLACK}{Back.WHITE}[server]{Style.RESET_ALL} {s}')
        elif data['type'] == 'chat':
            author = self.color_player(data['author'])
            for s in data['content'].splitlines():
                print(f'{author}> {s}')
        elif data['type'] == 'play':
            print(self.color_player(data['player']), data['cards'])
        elif data['type'] == 'rating_update':
            print('k = ', data['k'])
            for d in data['delta']:
                name, delta, rating = d['name'], d['delta'], d['rating']
                print(self.color_player(name),
                      (Fore.RED if delta >= 0 else Fore.GREEN) + str(delta) + Style.RESET_ALL,
                      rating,
                      sep = '\t')
            self.player_roles.clear()
        elif data['type'] == 'error':
            print(f'{Fore.RED}[error] {data["what"]}{Style.RESET_ALL}')
        elif data['type'] == 'sync':
            for change in data['attr']:
                k, v = change['key'], change['val']
                if k == 'player_type':
                    print(f'You are {get_color_from_role(v)}{v}{Style.RESET_ALL} now')
                elif k == 'cards':
                    print(''.join(v))
                elif k == 'always_spectator':
                    if v:
                        print('You are an always spectator now.')
                    else:
                        print('You are a normal player now.')
        elif data['type'] == 'start':
            for i in data['players']:
                name, role = i['name'], i['role']
                self.player_roles[name] = role
                print(f'{self.color_player(name)}\t{role}')
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
            description='vanilla client of ddz_py')
    parser.add_argument('hostname', help='the hostname of the ddz_py server')
    parser.add_argument('port', help='the port of the ddz_py server', type=int)
    parser.add_argument('name', help='your username')

    args = parser.parse_args()

    just_fix_windows_console()

    client = DdzClientDeluxe(args.hostname, args.port, args.name)
    asyncio.run(client.run())
