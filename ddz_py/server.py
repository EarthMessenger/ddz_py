import argparse
import asyncio
import dbm
import json
import math
import random

from typing import Optional, Union

from .protocol import *
from .card import suit_cards, is_bomb, card_rank
from .data import DdzPlayer

class Player(DdzPlayer):
    def __init__(self, writer: asyncio.StreamWriter, name: str):
        DdzPlayer.__init__(self, name)
        self.writer = writer

    async def send(self, msg: str):
        self.writer.write(encode_msg(msg))
        await self.writer.drain()

    async def tell(self, msg: str):
        await self.send(json.dumps({'type': 'tell', 'content': msg}))

    async def sync_data(self, keys: list[str]):
        data = {
                'type': 'sync',
                'attr': list(map(
                    lambda k: {'key': k, 'val': getattr(self, k)}, keys))}
        await self.send(json.dumps(data))

class DdzStatusWaitForLandlord:
    def __init__(self, players: list[Player], landlord_cards: list[str]):
        self.players = players
        self.landlord_cards = landlord_cards
        self.landlord_cards.sort(key = lambda x : card_rank[x])

class DdzStatusStarted:
    def __init__(self, initial_K: int, player_ord: list[Player]):
        self.current_K = initial_K
        self.player_ord = player_ord
        self.idx = 0
        self.played_stack: list[tuple[Player, str]] = []

    def front(self):
        return self.player_ord[self.idx]

    def shift(self, dis):
        self.idx = (self.idx + dis) % len(self.player_ord)

    def incr_k(self):
        self.current_K <<= 1

    def decr_k(self):
        self.current_K >>= 1;

def get_rating(db, name: str) -> float:
    res = db.get(name.encode())
    if res == None:
        return 1500.0
    else:
        return float(res.decode())

def set_rating(db, name: str, rating: float):
    db[name.encode()] = str(rating).encode()

class DdzServer:
    def __init__(self, addr: str, port: int, rating_db_path: str):
        self.addr = addr
        self.port = port
        self.players: list[Player] = []
        self.rating_db_path = rating_db_path
        self.initial_K = 32

        self.status: Union[None, DdzStatusWaitForLandlord, DdzStatusStarted] = None

    def choose_players(self, n):
        candidate_players = list(filter(lambda p : not p.always_spectator, self.players))
        if len(candidate_players) < n:
            raise Exception('no enough players')
        return random.sample(candidate_players, n)

    async def deal_cards(self, player_cnt: int, cards_each: int, suit: int):
        await self.cleanup()

        players = self.choose_players(player_cnt)

        c = list(suit_cards * suit)
        random.shuffle(c)

        pos = 0
        for p in players:
            p.player_type = 'undetermined'
            p.add_cards(c[pos:pos + cards_each])
            pos += cards_each

        self.status = DdzStatusWaitForLandlord(players, c[pos:])

        await self.broadcast(f'''Game is going to start! Players: {','.join(sorted(p.name for p in players))}.
Use `/become_landlord' to become landlord.''')

        await asyncio.gather(*(
            p.sync_data(['player_type', 'cards']) for p in players
            ))

    async def become_landlord(self, landlord: Player):
        if not isinstance(self.status, DdzStatusWaitForLandlord):
            raise Exception('You can\'t become landlord now.')
        
        landlord_cards = self.status.landlord_cards
        players = self.status.players

        landlord.add_cards(landlord_cards)

        def pop_insert_front(arr: list[Player], ele: Player):
            arr.insert(0, arr.pop(arr.index(ele)))

        pop_insert_front(players, landlord)

        cnt = 1
        for p in players:
            if p == landlord:
                p.player_type = 'landlord'
            else:
                p.player_type = f'peasant {cnt}'
                cnt += 1

        self.status = DdzStatusStarted(self.initial_K, players)

        await asyncio.gather(*(
            p.sync_data(['player_type', 'cards']) for p in players
            ))

        await self.broadcast(f'Landlord\'s extra cards are: {"".join(landlord_cards)}.')

        await self.send_all(json.dumps({
            'type': 'start',
            'players': list(map(
                lambda p : {'name': p.name, 'role': p.player_type},
                players))}))

    async def set_all_spectator(self):
        tasks = []
        for p in self.players:
            if not p.player_type.startswith('spectator'):
                p.player_type = 'spectator'
                p.cards = []
                tp = asyncio.create_task(p.sync_data(['player_type', 'cards']))
                tasks.append(tp)
        await asyncio.gather(*tasks)

    async def cleanup(self):
        self.status = None
        await self.set_all_spectator()

    async def exec_command(self, executor: Player, cmd: str):
        cmds = cmd.split()
        if len(cmds) == 0:
            return
        if cmds[0] == 'start':
            await self.deal_cards(3, 17, 1)
        elif cmds[0] == 'start4':
            await self.deal_cards(4, 25, 2)
        elif cmds[0] == 'list':
            msg = '\n'.join(map(lambda p : f'{p.name} [{p.player_status_abbr()}]', self.players))
            await executor.tell(msg)
        elif cmds[0] == 'rating':
            ratings = []
            with dbm.open(self.rating_db_path, 'c') as db:
                if len(cmds) == 1:
                    ratings.append((executor.name, float(str(get_rating(db, executor.name)))))
                else:
                    for i in cmds[1:]:
                        ratings.append((i, float(str(get_rating(db, i)))))
            msg = '\n'.join((f'{r[0]}\t{r[1]:.3f}' for r in ratings))
            await executor.tell(msg)
        elif cmds[0] == 'remain':
            remain = []
            if len(cmds) == 1:
                for p in self.players:
                    if not p.player_type.startswith('spectator'):
                        remain.append((p.name, len(p.cards)))
            else:
                for i in cmds[1:]:
                    for p in self.players:
                        if p.name == i:
                            remain.append((i, len(p.cards)))
                            break
            msg = '\n'.join((f'{r[0]}\t{r[1]}' for r in remain))
            await executor.tell(msg)
        elif cmds[0] == 'toggle_spectator':
            executor.always_spectator = not executor.always_spectator
            await executor.sync_data(['always_spectator'])
        elif cmds[0] == 'undo':

            if len(self.status.played_stack) == 0:
                raise Exception('No one played before')

            if self.status.played_stack[-1][0] != executor:
                raise Exception(f'The last player is not {executor.name} (expect {self.status.played_stack[-1][0].name})')

            _, cards = self.status.played_stack.pop()
            if is_bomb(cards):
                self.status.decr_k()

            executor.add_cards(cards)

            self.status.shift(-1)

            await self.broadcast(f'{executor.name} undos: {"".join(cards)}')
            await executor.sync_data(['cards'])
        elif cmds[0] == 'become_landlord':
            await self.become_landlord(executor)
        elif cmds[0] == 'help':
            await executor.tell("""Avaliable Commands:
/start, /start4, /list, /rating, /remain, /toggle_spectator, /undo, /become_landlord""")
        else:
            raise Exception('unknown command')

    def get_playing_players(self) -> list[Player]:
        res = []
        for p in self.players:
            if not p.name.startswith('spectator'):
                res.append(p)
        return res

    def update_rating(self, landlord_wins: bool) -> list[tuple[str, float, float]]:
        players = self.get_playing_players()

        landlord = list(filter(lambda p : p.player_type.startswith('landlord'), players))
        peasants = list(filter(lambda p : p.player_type.startswith('peasant'), players))

        if len(landlord) != 1:
            raise Exception('there should be exactly 1 landlord, cannot calculate rating')

        if len(peasants) == 0:
            raise Exception('no farmers, cannot calculate rating')

        landlord_delta = 0.0
        peasants_delta: list[float] = []

        info: list[tuple[str, float, float]] = []

        with dbm.open(self.rating_db_path, 'c') as db:
            landlord_rating = get_rating(db, landlord[0].name)
            peasants_rating = list(map(lambda p : get_rating(db, p.name), peasants))

            for p in peasants_rating:
                diff = (p - landlord_rating) / 400
                if abs(diff) < 100:
                    exp = 1 / (1 + 10**(diff))
                else:
                    exp = diff < 0

                delta = self.status.current_K * (landlord_wins - exp)

                landlord_delta += delta
                peasants_delta.append(-delta)

            set_rating(db, landlord[0].name, landlord_rating + landlord_delta)
            info.append((landlord[0].name, landlord_delta, landlord_rating + landlord_delta))
            for p, pr, pd in zip(peasants, peasants_rating, peasants_delta):
                set_rating(db, p.name, pr + pd)
                info.append((p.name, pd, pr + pd))

        info.sort(key = lambda d : -d[1])
        return info

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):

        async def read_join_name() -> str:
            length = int.from_bytes(await reader.readexactly(4), byteorder = 'big')
            body = json.loads(await reader.readexactly(length))
            if body['type'] != 'join':
                raise Exception('wrong message type')
            name = body['name']
            if any((name == p.name for p in self.players)):
                raise Exception('player is already in the server')
            return name

        try:
            name = await read_join_name()
        except Exception as e:
            print(e)
            writer.close()
            await writer.wait_closed()
            return

        await self.broadcast(f'{name} joined the game')

        player = Player(writer, name)
        self.players.append(player)

        while True:
            try: 
                length = int.from_bytes(await reader.readexactly(4), byteorder = 'big')
                body = json.loads(await reader.readexactly(length))
            except:
                break

            if body['type'] == 'chat':
                await self.send_all(json.dumps({
                    'type': 'chat',
                    'author': name,
                    'content': body['content']}))
            elif body['type'] == 'play':
                if player.player_type.startswith('spectator'):
                    continue

                if not isinstance(self.status, DdzStatusStarted):
                    await player.tell('Game isn\'t started')
                    continue

                if self.status.front() != player:
                    await player.tell(f'Not your turn! (expect {self.status.front().name})')
                    continue

                cards = list(body['cards'])
                if not player.check_have_cards(cards):
                    await player.tell('You don\'t have these cards')
                    continue
                player.remove_cards(cards)
                
                self.status.shift(1);

                self.status.played_stack.append((player, cards))
                await player.sync_data(['cards'])

                await self.send_all(json.dumps({
                    'type': 'play',
                    'player': name,
                    'cards': ''.join(cards)}))

                if is_bomb(cards):
                    self.status.incr_k()

                if len(player.cards) == 0:
                    try:
                        delta = self.update_rating(player.player_type.startswith('landlord'))
                        await self.send_all(json.dumps({
                            'type': 'rating_update',
                            'k': self.status.current_K,
                            'delta': list(map(
                                lambda d: {'name': d[0],
                                           'delta': d[1],
                                           'rating': d[2]}, delta))}))
                        await self.cleanup()
                    except Exception as e:
                        print(e)
                        await self.send_all(json.dumps({
                            'type': 'error',
                            'what': str(e)}))
            elif body['type'] == 'cmd':
                try:
                    await self.exec_command(player, body['cmd'])
                except Exception as e:
                    print(e)
                    await player.send(json.dumps({
                        'type': 'error',
                        'what': str(e)}))

        self.players.remove(player) 

        # if the player is in the game, then the game should end?
        if not player.player_type.startswith('spectator'):
            await self.cleanup()

        await self.broadcast(f'{name} exited.')
        player.writer.close()
        await player.writer.wait_closed()

    async def broadcast(self, msg: str):
        await self.send_all(json.dumps({'type': 'tell', 'content': msg}))

    async def send_all(self, msg: str):
        bmsg = encode_msg(msg)
        for p in self.players:
            p.writer.write(bmsg)
        await asyncio.gather(*(p.writer.drain() for p in self.players))

    async def run(self):
        self.server = await asyncio.start_server(self.handle, self.addr, self.port)

        addrs = ', '.join(str(sock.getsockname()) for sock in self.server.sockets)
        print(f'Serving on {addrs}')

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
