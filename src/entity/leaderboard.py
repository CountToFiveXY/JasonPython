"""Leaderboard entities stored in Firestore."""

from pydantic import BaseModel


TRACKS_PER_MAP = 2


class Track(BaseModel):
    """One of the tracks belonging to a single map."""

    id: str
    name: str


class GameMap(BaseModel):
    """A map and its fixed set of tracks."""

    id: str
    name: str
    tracks: list[Track]


class LapTime(BaseModel):
    """A car's recorded time on one track."""

    car: str
    seconds: float
