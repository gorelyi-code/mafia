import asyncio

from lib.latch import Latch

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
