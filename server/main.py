import os
from concurrent import futures
from threading import Lock, Condition
from random import sample, seed
import asyncio
from copy import copy

import grpc
from google.protobuf.empty_pb2 import Empty
from mafia_pb2 import Username, Users, StartGameResponse, EndDayResponse, CheckMafiaResponse, Winner, EndNightResponse, Roles
from mafia_pb2_grpc import MafiaServicer, add_MafiaServicer_to_server


class Latch:
    def __init__(self, count, callback):
        self.cur = 0
        self.count = count
        self.callback = callback

    def __call__(self, *args):
        self.cur += 1
        if self.cur == self.count:
            self.cur = 0
            self.callback(*args)


class MafiaGame:
    def __init__(self, player_roles):
        self.player_roles = player_roles
        self.players_alive = [username for username in player_roles]

        self.ready_to_wake = False
        self.waiting = Latch(4, self.WakeEveryone)
        self.not_waiting = Latch(4, self.SleepEveryone)
        
        self.execute_votes = {username: 0 for username in player_roles}
        self.end_voting = False
        self.voted = Latch(4, self.EndVoting)
        self.know_executed = Latch(4, self.StartVoting)

        self.mafia = ''
        self.know_mafia = Latch(4, self.ResetMafia)

    def WakeEveryone(self):
        self.ready_to_wake = True

    def SleepEveryone(self):
        self.ready_to_wake = False

    def EndVoting(self):
        self.end_voting = True

    def StartVoting(self, player_executed):
        self.end_voting = False

        if player_executed:
            self.players_alive.remove(player_executed)

    def ResetMafia(self):
        self.mafia = ''

    async def GetPlayerRole(self, username):
        return self.player_roles[username]

    async def GetRoles(self):
        return self.player_roles

    async def GetPlayersAlive(self):
        return self.players_alive

    async def SetKilled(self, username):
        self.killed = username

    async def GetKilled(self):
        if self.killed in self.players_alive:
            self.players_alive.remove(self.killed)

        return self.killed

    async def WaitNight(self):
        self.waiting()

        while not self.ready_to_wake:
            await asyncio.sleep(0.001)

        self.not_waiting()

    async def CheckWinner(self):
        civilians_left = 3
        for player, role in self.player_roles.items():
            if role == 'Мафия' and player not in self.players_alive:
                return 'Мирные'

            if role != 'Мафия' and player not in self.players_alive:
                civilians_left -= 1

        if civilians_left == 1:
            return 'Мафия'
        else:
            return ''

    async def VoteExecute(self, username):
        self.voted()

        if username:
            self.execute_votes[username] += 1
        
        while not self.end_voting:
            await asyncio.sleep(0.001)

        max_votes = 0
        player_executed = ''

        for player, votes in self.execute_votes.items():
            if votes > max_votes:
                max_votes = votes
                player_executed = player
            elif votes == max_votes:
                player_executed = ''

        self.know_executed(player_executed)

        return player_executed

    async def PublishMafia(self):
        for player, role in self.player_roles.items():
            if role == 'Мафия':
                self.mafia = player

    async def GetMafia(self):
        mafia = self.mafia

        self.know_mafia()

        return mafia


class Mafia(MafiaServicer):
    ROLES = ['Мафия', 'Комиссар', 'Мирный', 'Мирный']

    def __init__(self):
        self.users = set()

        self.games = dict()

        self.users_left = Latch(4, self.ResetUsers)
        self.users_ending = Latch(4, self.DeleteGame)

    def ResetUsers(self):
        self.users = set()

    def DeleteGame(self, game_id):
        del self.games[game_id]

    async def Connect(self, request, context):
        username = request.name

        users = set()

        self.users.add(username)

        while len(users) != 4:
            if users != self.users:
                users = copy(self.users)
                yield Users(username=[Username(name=name) for name in self.users])
        
            await asyncio.sleep(0.01)

        self.users_left()
    
    async def Disconnect(self, request, context):
        username = request.name

        self.users.remove(username)

        return Empty()

    async def StartGame(self, request, context):
        players = [player.name for player in request.players.username]

        game_hash = hash(tuple(players))

        seed(game_hash)

        if game_hash not in self.games:
            game = MafiaGame(dict(zip(players, sample(self.ROLES, k=4))))

            self.games[game_hash] = game
        else :
            game = self.games[game_hash]

        role = await game.GetPlayerRole(request.player.name)

        return StartGameResponse(game_id=game_hash, role=role)

    async def EndDay(self, request, context):
        game = self.games[request.game_id]

        player_role = await game.GetPlayerRole(request.username.name)

        if player_role in ['Комиссар', 'Мафия']:
            return EndDayResponse(do_action=True)
        else:
            return EndDayResponse(do_action=False)

    async def GetPlayersAlive(self, request, context):
        game = self.games[request.game_id]

        users = await game.GetPlayersAlive()

        return Users(username=[Username(name=username) for username in users])

    async def CheckMafia(self, request, context):
        game = self.games[request.info.game_id]
        player = request.player.name

        role = await game.GetPlayerRole(player)

        return CheckMafiaResponse(is_mafia=role == 'Мафия')

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

        mafia = await game.GetMafia()

        killed = await game.GetKilled()

        return EndNightResponse(killed=Username(name=killed), mafia=Username(name=mafia))

    async def CheckWinner(self, request, context):
        game = self.games[request.game_id]

        winner = await game.CheckWinner()

        return Winner(winner=winner)

    async def Execute(self, request, context):
        game = self.games[request.info.game_id]

        player_excuted = await game.VoteExecute(request.player.name)

        return Username(name=player_excuted)
    
    async def GetRoles(self, request, context):
        game = self.games[request.game_id]

        roles = await game.GetRoles()

        self.users_ending(request.game_id)

        return Roles(roles=roles)


async def serve():
    server = grpc.aio.server()
    add_MafiaServicer_to_server(Mafia(), server)
    listen_addr = f'0.0.0.0:{os.environ.get("SERVER_PORT", 50051)}'
    server.add_insecure_port(listen_addr)
    await server.start()
    await server.wait_for_termination()


if __name__ == '__main__':
    asyncio.run(serve())