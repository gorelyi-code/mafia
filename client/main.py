import asyncio
from random import choice
from aio_pika import ExchangeType, connect, Message, DeliveryMode
from concurrent.futures import ThreadPoolExecutor
from signal import SIGINT

import grpc
from proto.mafia_pb2 import Username, StartGameRequest, PlayerRequest, PlayerInfo
from proto.mafia_pb2_grpc import MafiaStub


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
    response = await stub.StartGame(StartGameRequest(player=username, players=users))

    role = response.role
    print(f'You are {role}')

    return PlayerInfo(game_id=response.game_id, username=username), role


async def end_day(player_info):
    response = await stub.EndDay(player_info)
    return response.do_action


async def test_mafia(player_info):
    print('Please choose the player to test for being mafia')

    if auto_mode:
        players_alive = await get_alive(player_info)
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


async def kill(player_info):
    print('Please choose the player who will be killed')

    if auto_mode:
        players_alive = await get_alive(player_info)
        if username.name in players_alive:
            players_alive.remove(username.name)

        player = Username(name=choice(players_alive))

        print(f'You decided to kill {player.name}')
    else:
        player = Username(name=input())

    await stub.Kill(PlayerRequest(info=player_info, player=player))


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

        await queue.bind(exchange, routing_key=str(game_id))

        await queue.consume(on_message)

        while True:
            text = await ainput()
            if not text:
                break
        
            message = Message(f'{username.name}: {text}'.encode(), delivery_mode=DeliveryMode.PERSISTENT)

            await exchange.publish(message, routing_key=str(game_id))

    print(f'You have left {name} chat')


async def game():
    global alive, stub, should_leave

    alive = True
    should_leave = False

    async with grpc.aio.insecure_channel('server:50051') as channel:
        stub = MafiaStub(channel)

        users = await join_lobby()
        if should_leave:
            return

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


if __name__ == '__main__':
    while True:
        print('Welcome to SOAmafia!')
        print('What would you like to do?')
        print('A: Play game')
        print('B: Inspect statistics (WIP)')
        print('C: Exit')
        match input():
            case 'A':
                print('Please, tell me your name: ', end='')
                username = Username(name=input())

                print('Do you want to play in auto mode? (Yes/No)')
                auto_mode = True if input() == 'Yes' else False

                while True:
                    asyncio.run(game())

                    print('Would you like to play again? (Yes/No)')
                    if input() != 'Yes':
                        break
            case 'B':
                pass
            case 'C':
                break
