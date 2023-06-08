from pydantic import BaseModel
from datetime import timedelta

class PlayerProfile(BaseModel):
    username: str
    picture: str
    sex: str
    email: str

class PlayerStatistics(BaseModel):
    profile: PlayerProfile
    games_played: int
    games_won: int
    games_lost: int
    time_played: timedelta
