import argparse
import asyncio
import dbm
import math
import random
from collections.abc import MutableMapping

from .protocol import *
from . import card

class Player:
    def __init__(self, writer: asyncio.StreamWriter, name: str, player_type: int):
        self.writer = writer
        self.name = name
        self.player_type = player_type
        self.card_count = 0

async def read_join_name(reader: asyncio.StreamReader) -> str:
    try:
        header = await reader.readexactly(5)
        msg_type, msg_length = decode_header(header)
        if msg_type != ClientMsgType.JOIN:
            return ''
        body = (await reader.readexactly(msg_length)).decode()
        return body
    except:
        return ''

def get_rating(db: MutableMapping[bytes, bytes], name: str) -> float:
    res = db.get(name.encode())
    if res == None:
        return 1500.0
    else:
        return float(res)

def set_rating(db: MutableMapping[bytes, bytes], name: str, rating: float):
    db[name.encode()] = str(rating).encode()

class DdzServer:
    def __init__(self, addr: str, port: int, rating_db_path: str):
        self.addr = addr
        self.port = port
        self.player_list: list[Player] = []
        self.joined_name: list[str] = []
        self.rating_db_path = rating_db_path

    async def deal_cards(self):
        if len(self.player_list) < 3:
            raise Exception('no enough players')

        for p in self.player_list:
            p.player_type = PlayerType.SPECTATOR
            p.card_count = 0

        players = random.sample(self.player_list, 3)

        suit_cards = list(card.suit_cards)
        random.shuffle(suit_cards)
        lord_cards = suit_cards[:20]
        farmer1_cards = suit_cards[20:37]
        farmer2_cards = suit_cards[37:]

        players[0].player_type = PlayerType.LORD
        players[0].card_count = 20

        players[1].player_type = PlayerType.FARMER
        players[1].card_count = 17

        players[2].player_type = PlayerType.FARMER
        players[2].card_count = 17

        asyncio.gather(
                self.deal_cards_to(players[0], lord_cards),
                self.deal_cards_to(players[1], farmer1_cards),
                self.deal_cards_to(players[2], farmer2_cards))

        await self.broadcast(f'lord: {players[0].name}, farmer 1: {players[1].name}, farmer 2: {players[2].name}')

    async def deal_cards_to(self, player: Player, cards: list[str]):
        await self.send_to(player, ''.join(cards), ServerMsgType.DEAL)

    async def set_all_spectator(self):
        for p in self.player_list:
            p.player_type = PlayerType.SPECTATOR
            p.card_count = 0

        tasks = []
        for p in self.player_list:
            tasks.append(self.deal_cards_to(p, []))
        for i in tasks:
            await i

    async def exec_command(self, executor: Player, cmd: str):
        cmds = cmd.split()
        if len(cmds) == 0:
            return
        if cmds[0] == 'add':
            executor.card_count += len(cmds[1])
        elif cmds[0] == 'start':
            await self.deal_cards()

    def get_playing_players(self) -> list[Player]:
        res = []
        for p in self.player_list:
            if p.player_type != PlayerType.SPECTATOR:
                res.append(p)
        return res

    def update_rating(self, winner: Player) -> list[tuple[str, float, float]]:
        players = self.get_playing_players()

        if len(players) != 3:
            raise Exception('not exactly 3 players in the game, cannot calcuate rating')

        lord = list(filter(lambda p : p.player_type == PlayerType.LORD, players))
        farmer = list(filter(lambda p : p.player_type == PlayerType.FARMER, players))

        if len(lord) != 1 or len(farmer) != 2:
            raise Exception('not 1 lord and 2 farmers, cannot calcuate rating')

        with dbm.open(self.rating_db_path, 'c') as db:
            lord_rating = get_rating(db, lord[0].name)
            farmer_rating = list(map(lambda n : get_rating(db, n.name), farmer))
            exp = 1 / (1 + 10**((max(farmer_rating) - lord_rating) / 400))
            lord_delta = 64 * (exp - (winner.name != lord[0].name))
            farmer_delta = -lord_delta / 2
            set_rating(db, lord[0].name, lord_rating + lord_delta)
            set_rating(db, farmer[0].name, farmer_rating[0] + farmer_delta)
            set_rating(db, farmer[1].name, farmer_rating[1] + farmer_delta)

        delta = [(lord[0].name, lord_delta, lord_rating + lord_delta),
                 (farmer[0].name, farmer_delta, farmer_rating[0] + farmer_delta),
                 (farmer[1].name, farmer_delta, farmer_rating[1] + farmer_delta)]
        delta.sort(key = lambda d : -math.inf if d[0] == winner.name else -d[1])
        return delta

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        name = await read_join_name(reader)

        if not name or name in self.joined_name:
            writer.close()
            await writer.wait_closed()
            return

        print(f'{name} joined. ')

        player = Player(writer, name, PlayerType.SPECTATOR)
        self.player_list.append(player)
        self.joined_name.append(name)

        while True:
            try: 
                header = await reader.readexactly(5)
                msg_type, msg_length = decode_header(header)
                body = (await reader.readexactly(msg_length)).decode()
            except:
                break
            print(f'{name} sent {header!r}({msg_type}, {msg_length}) {body}')
            if msg_type == ClientMsgType.CHAT:
                await self.broadcast(f'{name} {body}')
            elif msg_type == ClientMsgType.PLAY:
                await self.broadcast(f'{name} {body}')
                player.card_count -= len(body)
                if player.card_count == 0:
                    if player.player_type != PlayerType.SPECTATOR:
                        try:
                            delta = self.update_rating(player)
                            print(delta)
                            msg = '\n'.join((f'{d[0]}\t{d[1]:+.3f}\t{d[2]:.3f}' for d in delta))
                            await self.broadcast(msg)
                            await self.set_all_spectator()
                        except Exception as e:
                            print(e)
                elif player.card_count <= 2:
                    await self.broadcast(f'{player.name} has only {player.card_count} card(s). ')
            elif msg_type == ClientMsgType.CMD:
                try:
                    await self.exec_command(player, body)
                except Exception as e:
                    print(e)
                    await self.send_to(player, str(e))

        print(f'{name} exited. ')

        self.player_list.remove(player)
        self.joined_name.remove(player.name)
        player.writer.close()
        await player.writer.wait_closed()

    async def send_to(self, player: Player, msg: str, msg_type: int = ServerMsgType.MSG):
        player.writer.write(encode_msg(msg_type, msg))
        await player.writer.drain()

    async def broadcast(self, msg: str):
        bmsg = encode_msg(ServerMsgType.MSG, msg)
        for p in self.player_list:
            p.writer.write(bmsg)
        for p in self.player_list:
            await p.writer.drain()

    async def run(self):
        self.server = await asyncio.start_server(self.handle, self.addr, self.port)
        async with self.server:
            await self.server.serve_forever()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
            description='client of ddz_py')
    parser.add_argument('addr', help='bind to this address')
    parser.add_argument('port', help='bind to this port', type=int)
    parser.add_argument('rating_db_path', help='path of rating database')

    args = parser.parse_args()
    server = DdzServer(args.addr, args.port, args.rating_db_path)
    asyncio.run(server.run())
