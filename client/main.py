import grpc
from google.protobuf.empty_pb2 import Empty
from mafia_pb2 import Username, StartGameRequest, PlayerRequest, PlayerInfo
from mafia_pb2_grpc import MafiaStub

from random import choice
import asyncio


async def check_winner(stub, player_info):
    response = await stub.CheckWinner(player_info)
    winner = response.winner
    if winner:
        print('The game has finished')
        print(f'The winner is {winner}')
        print('Thanks for playing the game!')

        print('Player roles:')
        response = await stub.GetRoles(player_info)
        for player, role in response.roles.items():
            print(f'{player}: {role}')

        return True
    return False


async def game(username):
    print('Do you want to play in auto mode? (Yes/No)')
    auto_mode = True if input() == 'Yes' else False

    async with grpc.aio.insecure_channel('server:50051') as channel:
        stub = MafiaStub(channel)

        async for users in stub.Connect(username):
            if users.username:
                print('Users:', end=' ')
                print(*[user.name for user in users.username], sep=', ')

                if not auto_mode:
                    print('The game will start when 4 people join')
                    print('Would you like to quit? (Yes/No)')
                    if input() == 'Yes':
                        await stub.Disconnect(username)
                        exit()

                if len(users.username) == 4:
                    break

        response = await stub.StartGame(StartGameRequest(player=username, players=users))

        player_info = PlayerInfo(game_id=response.game_id, username=username)
        role = response.role

        print(f'You are {role}')

        alive = True

        while True:
            response = await stub.EndDay(player_info)
            do_action = response.do_action

            if do_action:
                if role == 'Комиссар':
                    print('Please choose the player to test for being mafia')

                    if auto_mode:
                        response = await stub.GetPlayersAlive(player_info)
                        players_alive = [user.name for user in response.username]
                        if username.name in players_alive:
                            players_alive.remove(username.name)

                        player = Username(name=choice(players_alive))

                        print(f'You chose {player.name}')
                    else:
                        player = Username(name=input())

                    response = await stub.CheckMafia(PlayerRequest(info=player_info, player=player))
                    if response.is_mafia:
                        print('The player you chose is mafia')
                        print('Would you like to publish the player who is mafia? (Yes/No)')
                        if auto_mode:
                            if choice([True, False]):
                                print('Yes')
                                await stub.PublishMafia(player_info)
                            else:
                                print('No')
                        else:
                            if input() == 'Yes':
                                await stub.PublishMafia(player_info)
                    else:
                        print('The player you chose is not mafia')
                elif role == 'Мафия':
                    print('Please choose the player who will be killed')

                    if auto_mode:
                        response = await stub.GetPlayersAlive(player_info)
                        players_alive = [user.name for user in response.username]
                        if username.name in players_alive:
                            players_alive.remove(username.name)

                        player = Username(name=choice(players_alive))

                        print(f'You decided to kill {player.name}')
                    else:
                        player = Username(name=input())

                    await stub.Kill(PlayerRequest(info=player_info, player=player))

            end_night_response = await stub.EndNight(player_info)
            player_killed = end_night_response.killed.name
            player_mafia = end_night_response.mafia.name

            print(f'This night mafia killed {player_killed}')
            if player_killed == username.name:
                print('You were killed, but you can still spectate the game')
                alive = False

            response = await stub.GetPlayersAlive(player_info)
            players_alive = [user.name for user in response.username]
            print('People still alive:', end=' ')
            print(*players_alive, sep=', ')

            if await check_winner(stub, player_info):
                break

            if player_mafia:
                print(f'{player_mafia} is mafia')

            print('Starting day execution')
            if alive:
                print('Please choose the player who will be executed (Empty to not execute anyone)')

                if auto_mode:
                    if username.name in players_alive:
                        players_alive.remove(username.name)
                    players_alive.append('')

                    player = Username(name=choice(players_alive))
                    print(player.name)
                else:
                    player = Username(name=input())
            else:
                player = Username(name='')

            response = await stub.Execute(PlayerRequest(info=player_info, player=player))
            player_dead = response.name

            if player_dead:
                print(f'Player {player_dead} has been executed')
            else:
                print(f'No one has been executed')

            if await check_winner(stub, player_info):
                break

if __name__ == '__main__':
    print('Please, tell me your name: ', end='')
    username = Username(name=input())

    while True:
        asyncio.run(game(username))

        print('Would you like to play again? (Yes/No)')
        if input() != 'Yes':
            break
