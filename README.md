# Вводная информация

В данном репозитории содержится реализация игры Мафия.

При подключении к серверу, игрок попадает в лобби, где логируется список ожидающих игроков. Игра начинается, если набралось 4 игрока. Есть возможность выбора режима игры (автоматический/ручной). В случае использования автоматического режима все действия будут логироваться.

В дневное время для всех живых игроков и в ночное время для мафии открывается чат, в котором можно обмениваться сообщениями. Для выхода из чата необходимо ввести пустое сообщение.

# Запуск и тестирование

Для начала необходимо собрать образы:

```
docker compose build
```

## Запуск сервера

```
docker compose up server rabbitmq
```

Необходимо запустить в отдельном терминале.

## Запуск клиента

```
docker compose run client
```

Необходимо запустить по одному клиенту на терминал. При запуске клиент спросит логин и предложит включить автоматический режим. После конца игры будет предложено начать новую игру. При завершении клиента (получении SIGINT) во время нахождения в лобби, игрок автоматически покидает сессию игры.


# Пример игры

```
Please, tell me your name: Mikhail
Do you want to play in auto mode? (Yes/No)
Yes
Users: Mikhail
Users: Mikhail, Friend1
Users: Mikhail, Friend1, Friend2
Users: Mikhail, Friend1, Friend2, Friend3
You are Мафия
Starting all chat. Type an empty message to end chat
Friend1: Hi!
Friend2: Wassup!
Hello!
Mikhail: Hello!
Friend3: How are you?

You have left all chat
Starting mafia chat. Type an empty message to end chat
I'm alone here ;-(
Mikhail: I'm alone here ;-(

You have left mafia chat
Please choose the player who will be killed
You decided to kill Friend1
This night mafia killed Friend1
People still alive: Mikhail, Friend2, Friend3
Starting day execution
Please choose the player who will be executed (Empty to not execute anyone)
Friend2
Player Friend2 has been executed
The game has finished
The winner is Мафия
Thanks for playing the game!
Player roles:
Mikhail: Мафия
Friend1: Комиссар
Friend2: Мирный
Friend3: Мирный
Would you like to play again? (Yes/No)
No
```