import argparse
import asyncio
import sys

from .client import DdzClient


# from https://stackoverflow.com/a/65326191/18180934
async def ainput():
    return (await asyncio.get_event_loop().run_in_executor(
            None, sys.stdin.readline))


class DdzClientVanilla:
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
                print(i['role'], i['name'], sep = '\t')
        else:
            print(data)

    async def receive_input(self):
        while True:
            msg = await ainput()
            if msg == '':
                break
            try:
                await self.client.handle_input(msg)
            except Exception as e:
                print(e)

    async def run(self):
        await self.client.connect()
        try:
            receive_task = asyncio.create_task(self.client.receive_message(self.receive_message_cb))
            await self.receive_input()
        finally:
            receive_task.cancel()
            await self.client.close_writer()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
            description='vanilla client of ddz_py')
    parser.add_argument('hostname', help='the hostname of the ddz_py server')
    parser.add_argument('port', help='the port of the ddz_py server', type=int)
    parser.add_argument('name', help='your username')

    args = parser.parse_args()

    client = DdzClientVanilla(args.hostname, args.port, args.name)
    asyncio.run(client.run())
