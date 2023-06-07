import uvicorn
from fastapi import FastAPI, HTTPException
from lib.common_objects import PlayerProfile

app = FastAPI()

players = dict()


@app.put('/register')
def register(player: PlayerProfile) -> None:
    players[player.username] = player


@app.post('/modify/{username}')
def modify(username: str, to_modify: str, value: str) -> None:
    if username not in players:
        raise HTTPException(404)
    
    if hasattr(players[username], to_modify):
        setattr(players[username], to_modify, value)
    else:
        raise HTTPException(405)
    


@app.get('/player/{username}')
def player(username: str) -> PlayerProfile:
    if username not in players:
        raise HTTPException(404)

    return players[username]


def main():
    uvicorn.run(app, host='0.0.0.0', port=13372)
    

if __name__ == '__main__':
    main()
