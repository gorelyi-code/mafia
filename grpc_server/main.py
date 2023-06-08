import os
import asyncio
import requests
from datetime import datetime
from random import sample
from copy import copy

import grpc
from google.protobuf.empty_pb2 import Empty
import proto.mafia_pb2_grpc as proto_grpc
import proto.mafia_pb2 as proto

from lib.latch import Latch
from lib.mafia_game import MafiaGame


class Mafia(proto_grpc.MafiaServicer):
    ROLES = ['Мафия', 'Комиссар', 'Мирный', 'Мирный']

    def __init__(self):
        self.users = set()

        self.games = dict()

        self.users_left = Latch(4, self.ResetUsers)
        self.users_ending = Latch(4, self.DeleteGame)

    def ResetUsers(self, users):
        game_hash = hash(tuple([user for user in users]))

        self.games[game_hash] = MafiaGame(dict(zip(users, sample(self.ROLES, k=4))))

        self.users = set()

    def DeleteGame(self, game_id, winner, roles, start):
        if winner == 'Мафия':
            for player, role in roles.items():
                if role == 'Мафия':
                    requests.post(f'http://rest_server:13372/result/{player}', params={'won': True, 'time': datetime.now() - start})
                else:
                    requests.post(f'http://rest_server:13372/result/{player}', params={'won': False, 'time': datetime.now() - start})
        elif winner == 'Мирные':
            for player, role in roles.items():
                if role == 'Мафия':
                    requests.post(f'http://rest_server:13372/result/{player}', params={'won': False, 'time': datetime.now() - start})
                else:
                    requests.post(f'http://rest_server:13372/result/{player}', params={'won': True, 'time': datetime.now() - start})

        del self.games[game_id]

    async def Connect(self, request, context):
        username = request.name

        users = set()

        self.users.add(username)

        while len(users) != 4:
            if users != self.users:
                users = copy(self.users)
                yield proto.Users(username=[proto.Username(name=name) for name in self.users])

            await asyncio.sleep(0.001)

        self.users_left(users)

    async def Disconnect(self, request, context):
        username = request.name

        self.users.remove(username)

        return Empty()

    async def StartGame(self, request, context):
        players = [player.name for player in request.players.username]

        game_hash = hash(tuple(players))

        game = self.games[game_hash]

        role = await game.GetPlayerRole(request.player.name)

        return proto.StartGameResponse(game_id=game_hash, role=role)

    async def EndDay(self, request, context):
        game = self.games[request.game_id]

        player_role = await game.GetPlayerRole(request.username.name)

        if player_role in ['Комиссар', 'Мафия']:
            return proto.EndDayResponse(do_action=True)
        else:
            return proto.EndDayResponse(do_action=False)

    async def GetPlayersAlive(self, request, context):
        game = self.games[request.game_id]

        users = await game.GetPlayersAlive()

        return proto.Users(username=[proto.Username(name=username) for username in users])

    async def CheckMafia(self, request, context):
        game = self.games[request.info.game_id]
        player = request.player.name

        role = await game.GetPlayerRole(player)

        return proto.CheckMafiaResponse(is_mafia=role == 'Мафия')

    async def PublishMafia(self, request, context):
        game = self.games[request.game_id]

        await game.PublishMafia()

        return Empty()

    async def Kill(self, request, context):
        game = self.games[request.info.game_id]
        player = request.player.name

        await game.SetKilled(player)

        return Empty()

    async def EndNight(self, request, context):
        game = self.games[request.game_id]

        await game.WaitNight()

        mafia = game.GetMafia()

        killed = game.GetKilled()

        return proto.EndNightResponse(killed=proto.Username(name=killed), mafia=proto.Username(name=mafia))

    async def CheckWinner(self, request, context):
        game = self.games[request.game_id]

        winner = game.CheckWinner()

        return proto.Winner(winner=winner)

    async def Execute(self, request, context):
        game = self.games[request.info.game_id]

        player_excuted = await game.VoteExecute(request.player.name)

        return proto.Username(name=player_excuted)

    async def GetRoles(self, request, context):
        game = self.games[request.game_id]

        roles = game.GetRoles()

        self.users_ending(request.game_id, game.CheckWinner(), roles, game.GetStart())

        return proto.Roles(roles=roles)


async def serve():
    server = grpc.aio.server()
    proto_grpc.add_MafiaServicer_to_server(Mafia(), server)
    listen_addr = f'0.0.0.0:{os.environ.get("SERVER_PORT", 50051)}'
    server.add_insecure_port(listen_addr)
    await server.start()
    await server.wait_for_termination()


if __name__ == '__main__':
    asyncio.run(serve())
