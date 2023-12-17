import argparse
import asyncio
import random
import dbm

from ddz_py.protocol import *
import ddz_py.card

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

class DdzServer:
    def __init__(self, addr: str, port: int, rating_db_path: str):
        self.addr = addr
        self.port = port
        self.player_list = []
        self.joined_name = []
        self.rating_db_path = rating_db_path

    async def deal_cards(self):
        if len(self.player_list) < 3:
            raise Exception('no enough players')

        for p in self.player_list:
            p.player_type = PlayerType.SPECTATOR
            p.card_count = 0

        players = random.sample(self.player_list, 3)

        suit_cards = list(ddz_py.card.suit_cards)
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

        tasks = []
        for p in self.player_list:
            if p == players[0]:
                tasks.append(self.deal_cards_to(p, lord_cards))
            elif p == players[1]:
                tasks.append(self.deal_cards_to(p, farmer1_cards))
            elif p == players[2]:
                tasks.append(self.deal_cards_to(p, farmer2_cards))
            else:
                tasks.append(self.deal_cards_to(p, []))
        for i in tasks:
            await i

        await self.broadcast(f'lord: {players[0].name}, farmer 1: {players[1].name}, farmer 2: {players[2].name}')

    async def deal_cards_to(self, player: Player, cards: list[str]):
        msg = encode_msg(ServerMsgType.DEAL, ''.join(cards))
        player.writer.write(msg)
        await player.writer.drain()

    async def exec_command(self, executor: Player, cmd: str):
        cmd = cmd.split()
        if len(cmd) == 0:
            return
        if cmd[0] == 'add':
            executor.card_count += len(cmd[1])
        elif cmd[0] == 'start':
            await self.deal_cards()

    def get_playing_players(self) -> list[Player]:
        res = []
        for p in self.player_list:
            if p.player_type != PlayerType.SPECTATOR:
                res.append(p)
        return res

    def update_rating(self, winner: Player) -> list[tuple[int, str, float, float]]:
        players = self.get_playing_players()
        players.sort(key = lambda p : -1 if p == winner else 0 if p.player_type == winner.player_type else p.card_count)
        delta = []
        with dbm.open(self.rating_db_path, 'c') as db:
            old_rating = []
            for p in players:
                rat = db.get(p.name)
                if not rat:
                    rat = 1500.0
                else:
                    rat = float(rat)
                old_rating.append(rat)
            f = [[1 / (1 + 10**((old_rating[j] - old_rating[i]) / 400)) for j in range(3)] for i in range(3)]
            g = [sum((f[j][i] if i != j else 0 for j in range(3))) for i in range(3)]
            new_rating = [old_rating[i] + 64 * (g[i] - i) for i in range(3)]
            for i, p in enumerate(players):
                db[p.name.encode()] = str(new_rating[i]).encode()
                delta.append((i, p.name, new_rating[i] - old_rating[i], new_rating[i]))
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
            print(f'{name} send {header}({msg_type}, {msg_length}) {body}')
            if msg_type == ClientMsgType.CHAT:
                await self.broadcast(f'{name} {body}')
            elif msg_type == ClientMsgType.PLAY:
                await self.broadcast(f'{name} {body}')
                player.card_count -= len(body)
                if player.card_count == 0:
                    delta = self.update_rating(player)
                    print(delta)
                    msg = '\n'.join((f'{d[0]}\t{d[1]}\t{d[2]:+.3f}\t{d[3]:.3f}' for d in delta))
                    await self.broadcast(msg)
                elif player.card_count <= 2:
                    await self.broadcast(f'{player.name} has only {player.card_count} card(s). ')
            elif msg_type == ClientMsgType.CMD:
                try:
                    await self.exec_command(player, body)
                except Exception as e:
                    print(e)

        print(f'{name} exited. ')

        self.player_list.remove(player)
        self.joined_name.remove(player.name)
        player.writer.close()
        await player.writer.wait_closed()

    async def broadcast(self, msg: str):
        msg = encode_msg(ServerMsgType.MSG, msg)
        for p in self.player_list:
            p.writer.write(msg)
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
