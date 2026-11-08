"""Data structures stored on disk as JSON."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Athlete:
    name: str
    club: str = ""


@dataclass
class Match:
    start: int  # second of the video the link should start from
    end: int  # last second the match scoreboard was on screen
    category: str
    round: str
    white: Athlete
    blue: Athlete


@dataclass
class VideoIndex:
    video_id: str
    title: str
    url: str
    duration: int
    matches: list[Match] = field(default_factory=list)

    def link(self, match: Match) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}&t={match.start}s"

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> VideoIndex:
        data = json.loads(path.read_text(encoding="utf-8"))
        matches = [
            Match(**{**m, "white": Athlete(**m["white"]), "blue": Athlete(**m["blue"])})
            for m in data.pop("matches", [])
        ]
        return cls(**data, matches=matches)
