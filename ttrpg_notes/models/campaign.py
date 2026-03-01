from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Kill:
    being: str
    count: int


@dataclass
class Character:
    id: str
    name: str


@dataclass
class Player:
    id: str
    name: str
    characters: list[Character] = field(default_factory=list)


@dataclass
class Session:
    id: str
    number: int
    name: str | None
    date: str           # ISO date "2024-01-15"
    summary: str
    kills: dict[str, list[Kill]] = field(default_factory=dict)  # character_id -> kills
    pre_notes: str = ""
    post_notes: str = ""
    dirty: bool = False  # not persisted


@dataclass
class Campaign:
    id: str
    name: str
    date_format: str    # Qt date format, e.g. "yyyy-MM-dd"
    players: list[Player] = field(default_factory=list)
    sessions: list[Session] = field(default_factory=list)
