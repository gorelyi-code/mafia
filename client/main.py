import asyncio
import os
import requests
import json
from random import choice
from aio_pika import ExchangeType, connect, Message, DeliveryMode
from concurrent.futures import ThreadPoolExecutor
from signal import SIGINT
from lib.common_objects import PlayerProfile

import grpc
import proto.mafia_pb2_grpc as proto_grpc
import proto.mafia_pb2 as proto


def clear():
    os.system('clear')


async def check_winner(player_info):
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


def leave():
    global should_leave
    should_leave = True

    asyncio.ensure_future(stub.Disconnect(username))


async def join_lobby():
    original = asyncio.get_running_loop().add_signal_handler(SIGINT, leave)

    async for users in stub.Connect(username):
        if should_leave:
            asyncio.get_running_loop().add_signal_handler(SIGINT, original)
            break

        if users.username:
            print('Users:', end=' ')
            print(*[user.name for user in users.username], sep=', ')

            if len(users.username) == 4:
                break

    asyncio.get_running_loop().add_signal_handler(SIGINT, original)

    return users


async def start(users):
    response = await stub.StartGame(proto.StartGameRequest(player=username, players=users))

    role = response.role
    print(f'You are {role}')

    return proto.PlayerInfo(game_id=response.game_id, username=username), role


async def end_day(player_info):
    response = await stub.EndDay(player_info)
    return response.do_action


async def test_mafia(player_info):
    print('Please choose the player to test for being mafia')

    if auto_mode:
        players_alive = await get_alive(player_info)
        if username.name in players_alive:
            players_alive.remove(username.name)

        player = proto.Username(name=choice(players_alive))

        print(f'You chose {player.name}')
    else:
        player = proto.Username(name=input())

    response = await stub.CheckMafia(proto.PlayerRequest(info=player_info, player=player))
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
            while True:
                publish = input()
                if publish == 'Yes':
                    await stub.PublishMafia(player_info)
                    break
                elif publish == 'No':
                    break
    else:
        print('The player you chose is not mafia')


async def kill(player_info):
    print('Please choose the player who will be killed')

    if auto_mode:
        players_alive = await get_alive(player_info)
        if username.name in players_alive:
            players_alive.remove(username.name)

        player = proto.Username(name=choice(players_alive))

        print(f'You decided to kill {player.name}')
    else:
        player = proto.Username(name=input())

    await stub.Kill(proto.PlayerRequest(info=player_info, player=player))


async def end_night(player_info):
    global alive

    end_night_response = await stub.EndNight(player_info)
    player_killed = end_night_response.killed.name
    player_mafia = end_night_response.mafia.name

    print(f'This night mafia killed {player_killed}')
    if player_killed == username.name:
        print('You were killed, but you can still spectate the game')
        alive = False

    if player_mafia:
        print(f'{player_mafia} is mafia')


async def get_alive(player_info):
    response = await stub.GetPlayersAlive(player_info)
    return [user.name for user in response.username]


async def print_alive(player_info):
    players_alive = await get_alive(player_info)
    print('People still alive:', end=' ')
    print(*players_alive, sep=', ')


async def execution(player_info):
    global alive

    print('Starting day execution')
    if alive:
        print('Please choose the player who will be executed (Empty to not execute anyone)')

        if auto_mode:
            players_alive = await get_alive(player_info)
            if username.name in players_alive:
                players_alive.remove(username.name)
            players_alive.append('')

            player = proto.Username(name=choice(players_alive))
            print(player.name)
        else:
            player = proto.Username(name=input())
    else:
        player = proto.Username(name='')

    response = await stub.Execute(proto.PlayerRequest(info=player_info, player=player))
    player_dead = response.name

    if player_dead:
        print(f'Player {player_dead} has been executed')

        if player_dead == username.name:
            print('You were killed, but you can still spectate the game')
            alive = False
    else:
        print(f'No one has been executed')

async def on_message(message):
    async with message.process():
        print(message.body.decode())


async def ainput():
    with ThreadPoolExecutor(1, "AsyncInput") as executor:
        return await asyncio.get_event_loop().run_in_executor(executor, input)


async def chat(name, game_id):
    print(f'Starting {name} chat. Type an empty message to end chat')

    connection = await connect("amqp://guest:guest@rabbitmq/")

    async with connection:
        channel = await connection.channel()

        exchange = await channel.declare_exchange(name, ExchangeType.DIRECT)

        queue = await channel.declare_queue(exclusive=True)

        await queue.bind(exchange, routing_key=game_id)

        await queue.consume(on_message)

        while True:
            text = await ainput()
            if not text:
                break

            message = Message(f'{username.name}: {text}'.encode(), delivery_mode=DeliveryMode.PERSISTENT)

            await exchange.publish(message, routing_key=game_id)

    print(f'You have left {name} chat')


async def game():
    global alive, stub, should_leave, auto_mode

    clear()

    while True:
        print('Do you want to play in auto mode? (Yes/No)')
        want_auto = input()
        if want_auto == 'Yes':
            auto_mode = True
            break
        elif want_auto == 'No':
            auto_mode = False
            break

    while True:
        clear()

        alive = True
        should_leave = False

        async with grpc.aio.insecure_channel('grpc_server:50051') as channel:
            stub = proto_grpc.MafiaStub(channel)

            users = await join_lobby()
            if should_leave:
                return

            clear()

            player_info, role = await start(users)

            while True:
                if alive:
                    await chat('all', player_info.game_id)

                do_action = await end_day(player_info)

                if do_action:
                    if role == 'Комиссар':
                        await test_mafia(player_info)
                    elif role == 'Мафия':
                        await chat('mafia', player_info.game_id)

                        await kill(player_info)

                await end_night(player_info)

                if await check_winner(player_info):
                    break

                await print_alive(player_info)

                await execution(player_info)

                if await check_winner(player_info):
                    break

        while True:
            print('Would you like to play again? (Yes/No)')
            one_more = input()
            if one_more == 'Yes':
                break
            elif one_more == 'No':
                return


def create_profile():
    print('picture:', end=' ')
    picture = input()

    print('sex:', end=' ')
    sex = input()

    print('email:', end=' ')
    email = input()

    player = PlayerProfile(username=username.name, picture=picture, sex=sex, email=email)

    requests.put(f'http://rest_server:13372/register', data=player.json())


def modify_profile():
    clear()

    while True:
        print('What would you like to modify? (username/picture/sex/email)')
        to_modify = input()

        print('What should the new value be?')
        value = input()

        response = requests.post(f'http://rest_server:13372/modify/{username.name}', params={'to_modify': to_modify, 'value': value})
        if response.status_code == 405:
            print('There is no such attribute! Please, try again')
        else:
            break
         

def get_profiles():
    while True:
        clear()

        print('Whose profiles would you like to check? Type usernames, separated with commas')
        usernames = input()
        response = requests.get(f'http://rest_server:13372/profile', params={'usernames': usernames})
        if response.status_code == 404:
            print('One of the players does not exist! Please, try again')
        else:
            clear()

            usernames = usernames.split(', ')

            for i, player_profile in enumerate(response.json()):
                print(f'{usernames[i]}:')
                for key, value in player_profile.items():
                    print(f'{key}: {value}')

        while True:
            print('Would you like to get other peoples` profiles? (Yes/No)')
            more_stat = input()
            if more_stat == 'Yes':
                break
            elif more_stat == 'No':
                return


def remove_profile():
    requests.delete(f'http://rest_server:13372/remove/{username.name}')


def get_statistics():
    while True:
        clear()

        print('Whose statistics would you like to check?')
        response = requests.get(f'http://rest_server:13372/statistics/{input()}')
        if response.status_code == 404:
            print('There is no such player! Please, try again')
        else:
            clear()

            print(response.text)

        while True:
            print('Would you like to get other person`s statistics? (Yes/No)')
            more_stat = input()
            if more_stat == 'Yes':
                break
            elif more_stat == 'No':
                return


def get_games():
    while True:
        clear()

        query = """
        {
            getGames {
                id
                scoreboard {
                    username
                    score
                }
                players
                comments
            }
        }
        """
        
        response = requests.post('http://graphql_server:13371/graphql', json={'query': query})

        for game_info in json.loads(response.content.decode())['data']['getGames']:
            print(f'Game {game_info["id"]}')
            print(f'Players: {game_info["players"]}')
            print('Scoreboard:')
            for player_score in game_info['scoreboard']:
                print(f'Player {player_score["username"]}: {player_score["score"]} games won')
            print('Comments:')
            for comment in game_info['comments']:
                print(comment)
            print()
        
        while True:
            print('Would you like to get all games again? (Yes/No)')
            games_again = input()
            if games_again == 'Yes':
                break
            elif games_again == 'No':
                return


def get_scoreboard():
    while True:
        clear()

        print('Enter the id of the game:', end=' ')
        game_id = input()

        query = f"""
        {{
            getScoreboard(id:"{game_id}") {{
                scoreboard {{
                    username
                    score
                }}
            }}
        }}
        """

        response = requests.post('http://graphql_server:13371/graphql', json={'query': query})

        for player_score in json.loads(response.content.decode())['data']['getScoreboard']['scoreboard']:
            print(f'Player {player_score["username"]}: {player_score["score"]} games won')

        while True:
            print('Would you like to get scoreboard of a different game? (Yes/No)')
            another_scoreboard = input()
            if another_scoreboard == 'Yes':
                break
            elif another_scoreboard == 'No':
                return


def add_comment():
    clear()

    print('Enter the id of the game:', end=' ')
    game_id = input()

    print('Enter the comment:', end=' ')
    comment = input()

    query = f"""
    {{
        addComment(id:"{game_id}", comment:"{comment}")
    }}
    """

    requests.post('http://graphql_server:13371/graphql', json={'query': query})


if __name__ == '__main__':
    clear()

    print('Please, tell me your name: ', end='')
    username = proto.Username(name=input())

    print('Please, fill in some info about you')
    create_profile()
    
    while True:
        clear()

        print(f'Welcome to SOAmafia, {username.name}!')
        print('What would you like to do?')
        print('A: Play game')
        print('B: Modify your profile')
        print('C: Get players` profiles')
        print('D: Get player statistics')
        print('E: Get games')
        print('F: Get game scoreboard')
        print('G: Add comment to game')
        print('H: Exit')
        option = input()

        match option:
            case 'A':
                asyncio.run(game())
            case 'B':
                modify_profile()
            case 'C':
                get_profiles()
            case 'D':
                get_statistics()
            case 'E':
                get_games()
            case 'F':
                get_scoreboard()
            case 'G':
                add_comment()
            case 'H':
                break

    remove_profile()
