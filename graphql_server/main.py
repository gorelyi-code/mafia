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
    id: int
    scoreboard: list[PlayerScore]
    players: list[str]
    comments: list[str] = field(default_factory=list) 

app = Flask(__name__)
CORS(app)

games: dict[int, GameInfo] = {
    '228': GameInfo(228, [PlayerScore('a', 0), PlayerScore('b', 1), PlayerScore('c', 1), PlayerScore('d', 1)], ['a', 'b', 'c', 'd']),
    '1337': GameInfo(1337, [PlayerScore('e', 1), PlayerScore('f', 0), PlayerScore('g', 0), PlayerScore('h', 0)], ['e', 'f', 'g', 'h']),
}


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
