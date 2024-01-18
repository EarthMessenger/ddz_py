import argparse
import asyncio
import sys

from .client import DdzClient
from .protocol import *

# from https://stackoverflow.com/a/65326191/18180934
async def ainput():
    return (await asyncio.get_event_loop().run_in_executor(
            None, sys.stdin.readline))

class DdzClientLight:
    def __init__(self, hostname: str, port: int, name: str):
        self.client = DdzClient(hostname, port, name)

    def receive_message_cb(self, msg: str):
        print(msg)

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

if __name__== '__main__':
    parser = argparse.ArgumentParser(
            description='vanilla client of ddz_py')
    parser.add_argument('hostname', help='the hostname of the ddz_py server')
    parser.add_argument('port', help='the port of the ddz_py server', type=int)
    parser.add_argument('name', help='your username')

    args = parser.parse_args()

    client = DdzClientLight(args.hostname, args.port, args.name)
    asyncio.run(client.run())
