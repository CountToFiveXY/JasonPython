"""Leaderboard entities stored in Firestore."""

from pydantic import BaseModel


TRACKS_PER_MAP = 2


#: Where a map with no recorded release order sorts: after every known one.
UNRELEASED_ORDER = 999


class Track(BaseModel):
    """One of the tracks belonging to a single map."""

    id: str
    name: str
    chinese_name: str = ""


class GameMap(BaseModel):
    """A map and its fixed set of tracks."""

    id: str
    name: str
    tracks: list[Track]
    chinese_name: str = ""
    #: Position in the game's release order, which is how maps are listed.
    release_order: int = UNRELEASED_ORDER


class LapTime(BaseModel):
    """A car's recorded time on one track."""

    car: str
    seconds: float
    #: Optional note about the trick used. Times recorded before this field
    #: existed read back as blank.
    trick: str = ""
