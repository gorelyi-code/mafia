import os
from concurrent import futures
from threading import Lock, Condition
from random import sample, seed

import grpc
from google.protobuf.empty_pb2 import Empty
from mafia_pb2 import Username, Users, StartGameResponse, EndDayResponse, CheckMafiaResponse, Winner, EndNightResponse, Roles
from mafia_pb2_grpc import MafiaServicer, add_MafiaServicer_to_server


class MafiaGame:
    def __init__(self, player_roles):
        self.player_roles = player_roles
        self.players_alive = [username for username in player_roles]

        self.waiting = 4
        self.next_waiting = 0
        
        self.voted = 0
        self.execute_votes = {username: 0 for username in player_roles}
        self.next_votes = 0
        self.people_knowing_executed=0

        self.mafia = ''
        self.knowing_mafia = 0

        self.lock = Lock()
        self.cv = Condition(self.lock)

    def GetPlayerRole(self, username):
        return self.player_roles[username]

    def GetRoles(self):
        return self.player_roles

    def GetPlayersAlive(self):
        with self.cv:
            return self.players_alive

    def SetKilled(self, username):
        self.killed = username

    def GetKilled(self):
        with self.cv:
            if self.killed in self.players_alive:
                self.players_alive.remove(self.killed)

        return self.killed

    def ResetWaiting(self):
        with self.cv:
            self.next_waiting += 1
            if self.next_waiting == 4:
                self.waiting = 4
                self.next_waiting = 0

    def WaitNight(self):
        with self.cv:
            self.waiting -= 1

            if self.waiting == 0:
                self.cv.notify_all()

            while self.waiting != 0:
                self.cv.wait()

    def CheckWinner(self):
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

    def ResetVotes(self):
        with self.cv:
            self.next_votes += 1
            if self.next_votes == 4:
                self.voted = 0
                self.next_votes = 0

    def VoteExecute(self, username):
        with self.cv:
            self.voted += 1

            if self.voted == 4:
                self.cv.notify_all()

            if username:
                self.execute_votes[username] += 1
            
            while self.voted != 4:
                self.cv.wait()

        max_votes = 0
        player_executed = ''

        for player, votes in self.execute_votes.items():
            if votes > max_votes:
                max_votes = votes
                player_executed = player
            elif votes == max_votes:
                player_executed = ''

        if player_executed:
            self.people_knowing_executed += 1
            if self.people_knowing_executed == 4:
                self.players_alive.remove(player_executed)
                self.people_knowing_executed = 0

        return player_executed

    def PublishMafia(self):
        with self.cv:
            for player, role in self.player_roles.items():
                if role == 'Мафия':
                    self.mafia = player

    def GetMafia(self):
        with self.cv:
            mafia = self.mafia
            self.knowing_mafia += 1
            if self.knowing_mafia == 4:
                self.mafia = ''
                self.knowing_mafia = 0
        return mafia


class Mafia(MafiaServicer):
    ROLES = ['Мафия', 'Комиссар', 'Мирный', 'Мирный']

    def __init__(self):
        self.users = dict()

        self.games = dict()

        self.lock = Lock()
        self.cv = Condition(self.lock)

        self.left_lobby = 0
        self.ready_to_end = 0

    def Connect(self, request, context):
        with self.cv:
            username = request.name

            self.users[username] = 0

            for user in self.users:
                self.users[user] += 1

            while True:
                while self.users[username] == 0:
                    self.cv.wait()

                self.users[username] -= 1
                yield Users(username=[Username(name=name) for name in self.users.keys()])

                if len(self.users) == 4:
                    self.cv.notify_all()

                    self.left_lobby += 1
                    if self.left_lobby == 4:
                        self.users = dict()
                        self.left_lobby = 0
                    break
    
    def Disconnect(self, request, context):
        with self.cv:
            self.cv.notify_all()

            username = request.name

            del self.users[username]

            for actions in self.users.values():
                actions += 1

            return Empty()

    def StartGame(self, request, context):
        players = [player.name for player in request.players.username]

        game_hash = hash(tuple(players))

        seed(game_hash)

        with self.cv:
            if game_hash not in self.games:
                game = MafiaGame(dict(zip(players, sample(self.ROLES, k=4))))

                self.games[game_hash] = game
            else :
                game = self.games[game_hash]

            return StartGameResponse(game_id=game_hash, role=game.GetPlayerRole(request.player.name))

    def EndDay(self, request, context):
        game = self.games[request.game_id]

        player_role = game.GetPlayerRole(request.username.name)

        if player_role in ['Комиссар', 'Мафия']:
            return EndDayResponse(do_action=True)
        else:
            return EndDayResponse(do_action=False)

    def GetPlayersAlive(self, request, context):
        game = self.games[request.game_id]

        return Users(username=[Username(name=username) for username in game.GetPlayersAlive()])

    def CheckMafia(self, request, context):
        game = self.games[request.info.game_id]
        player = request.player.name

        return CheckMafiaResponse(is_mafia=game.GetPlayerRole(player) == 'Мафия')

    def PublishMafia(self, request, context):
        game = self.games[request.game_id]

        game.PublishMafia()

        return Empty()

    def Kill(self, request, context):
        game = self.games[request.info.game_id]
        player = request.player.name

        game.SetKilled(player)

        return Empty()

    def EndNight(self, request, context):
        game = self.games[request.game_id]

        game.WaitNight()

        game.ResetWaiting()

        mafia = game.GetMafia()

        return EndNightResponse(killed=Username(name=game.GetKilled()), mafia=Username(name=mafia))

    def CheckWinner(self, request, context):
        game = self.games[request.game_id]

        winner = game.CheckWinner()

        return Winner(winner=winner)

    def Execute(self, request, context):
        game = self.games[request.info.game_id]

        player_excuted = game.VoteExecute(request.player.name)

        game.ResetVotes()

        return Username(name=player_excuted)
    
    def GetRoles(self, request, context):
        game = self.games[request.game_id]

        roles = game.GetRoles()

        with self.cv:
            self.ready_to_end += 1
            if self.ready_to_end == 4:
                del self.games[request.game_id]
                self.ready_to_end = 0

        return Roles(roles=roles)


server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
add_MafiaServicer_to_server(Mafia(), server)
listen_addr = f'0.0.0.0:{os.environ.get("SERVER_PORT", 50051)}'
server.add_insecure_port(listen_addr)
server.start()
server.wait_for_termination()
