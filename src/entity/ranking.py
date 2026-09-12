"""Ranking domain values."""

from enum import Enum


class CardType(str, Enum):
    SE = "SE"
    SP = "SP"
    CH = "CH"
