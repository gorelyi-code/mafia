from ariadne import load_schema_from_path, make_executable_schema, ObjectType, graphql_sync
from flask import Flask, request, jsonify
from flask_cors import CORS
from dataclasses import dataclass, asdict, field

@dataclass
class PlayerScore:
    username: str
    score: int

@dataclass
class GameInfo:
    id: str
    scoreboard: list[PlayerScore]
    players: list[str]
    comments: list[str] = field(default_factory=list) 

app = Flask(__name__)
CORS(app)

games: dict[str, GameInfo] = dict()


@app.route("/graphql", methods=["POST"])
def graphql_server():
    data = request.get_json()
    success, result = graphql_sync(schema, data, context_value=request, debug=app.debug)
    status_code = 200 if success else 400
    return jsonify(result), status_code


query = ObjectType("Query")


@query.field('getGames')
def resolve_getGames(obj, info):
    return [asdict(game_info) for game_info in games.values()]


@query.field('addGame')
def resolve_addGame(obj, info, id, players, scores):
    if id in games:
        return 'Game info already exists!'
    scoreboard = [PlayerScore(player, score) for player, score in zip(players, scores)]
    games[id] = GameInfo(id, scoreboard, players)


@query.field('getScoreboard')
def resolve_getScoreboard(obj, info, id):
    if id not in games:
        return {'error': 'Invalid ID'}
    else:
        return {'scoreboard': [asdict(player_score) for player_score in games[id].scoreboard]}


@query.field('addComment')
def resolve_addComment(obj, info, id, comment):
    if id not in games:
        return 'Invalid ID'
    else:
        games[id].comments.append(comment)


schema = make_executable_schema(load_schema_from_path("mafia.graphql"), query)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=13371)
