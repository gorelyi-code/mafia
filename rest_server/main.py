import uvicorn
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from lib.common_objects import PlayerProfile, PlayerStatistics
from datetime import timedelta
from borb.pdf import Document, Page, SingleColumnLayout, Paragraph, PDF, Image
from decimal import Decimal
from queue import Queue
from concurrent.futures import ThreadPoolExecutor

app = FastAPI()

players: dict[str, PlayerStatistics] = dict()
pdfs: dict[str, asyncio.Future] = dict()
queue = Queue()


@app.put('/register')
async def register(player: PlayerProfile) -> None:
    players[player.username] = PlayerStatistics(profile=player, games_played=0, games_won=0, games_lost=0, time_played=timedelta())


@app.post('/modify/{username}')
async def modify(username: str, to_modify: str, value: str) -> None:
    if hasattr(players[username].profile, to_modify):
        setattr(players[username].profile, to_modify, value)
    else:
        raise HTTPException(405)
    


@app.get('/profile')
async def profile(usernames: str) -> list[PlayerProfile]:
    result = []

    for username in usernames.split(', '):
        if username not in players:
            raise HTTPException(404)

        result.append(players[username].profile)
    
    return result


@app.delete('/remove/{username}')
async def remove(username: str) -> None:
    del players[username]


def generate_pdf(statistics: PlayerStatistics):
    pdf = Document()
    page = Page()
    pdf.add_page(page)
    layout = SingleColumnLayout(page)
    layout.add(Paragraph(f'Username: {statistics.profile.username}'))
    layout.add(Image(statistics.profile.picture, width=Decimal(256), height=Decimal(256)))
    layout.add(Paragraph(f'Sex: {statistics.profile.sex}'))
    layout.add(Paragraph(f'Email: {statistics.profile.email}'))
    layout.add(Paragraph(f'Games played: {str(statistics.games_played)}'))
    layout.add(Paragraph(f'Games won: {str(statistics.games_won)}'))
    layout.add(Paragraph(f'Games lost: {str(statistics.games_lost)}'))
    layout.add(Paragraph(f'Time played: {str(statistics.time_played).split(".")[0]}'))

    with open(f'{statistics.profile.username}.pdf', "wb") as pdf_file_handle:
        PDF.dumps(pdf_file_handle, pdf)


@app.get('/statistics/{username}')
async def statistics(username: str) -> str:
    if username not in players:
        raise HTTPException(404)
    
    pdfs[username] = asyncio.get_running_loop().create_future()

    queue.put(username)

    return f'http://127.0.0.1:13372/file/{username}.pdf'


@app.get('/file/{username}.pdf')
async def file(username: str) -> FileResponse:
    if username not in players:
        raise HTTPException(404)
    
    await pdfs[username]

    return FileResponse(f'{username}.pdf')


@app.post('/result/{username}')
async def result(username: str, won: bool, time: timedelta) -> None:
    if username not in players:
        raise HTTPException(404)

    players[username].games_played += 1
    if won:
        players[username].games_won += 1
    else:
        players[username].games_lost += 1
    players[username].time_played += time


def process_tasks():
    while True:
        username = queue.get()
        if username is None:
            break

        pdfs[username].set_result(generate_pdf(players[username]))


@app.on_event('startup')
async def startup():
    global fut, executor

    executor = ThreadPoolExecutor(1, "Tasks")
    fut = asyncio.get_event_loop().run_in_executor(executor, process_tasks)


@app.on_event('shutdown')
async def shutdown():
    queue.put(None)
    await fut
    executor.shutdown()


def main():
    uvicorn.run(app, host='0.0.0.0', port=13372)
    

if __name__ == '__main__':
    main()
