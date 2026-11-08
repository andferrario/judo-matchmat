"""From a video URL to the list of its matches."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from .models import Match, VideoIndex
from .scoreboard import Layout, Reader, Reading, is_visible, same_board, signature
from .youtube import Stream, open_video

Progress = Callable[[str], None]


@dataclass
class Scene:
    """Stretch of video during which the same scoreboard stays on screen."""

    start: int
    end: int
    times: list[int] = field(default_factory=list)


@dataclass
class Stats:
    samples: int = 0
    reads: int = 0
    bytes: int = 0


def scan(
    url: str,
    layout: Layout,
    step: int = 15,
    start: int = 0,
    end: int | None = None,
    workers: int = 8,
    progress: Progress = lambda _: None,
) -> tuple[VideoIndex, Stats]:
    video = open_video(url)
    end = min(end or video.duration, video.duration)
    stats = Stats()
    progress(f"{video.title} ({_hms(video.duration)})")

    # 1. Light 360p pass: keep only the fingerprint of the names area.
    times = list(range(start, end, step))
    sigs = []
    with ThreadPoolExecutor(workers) as pool:
        for i, (img, n) in enumerate(pool.map(lambda t: video.low.frame_at(t), times), 1):
            stats.bytes += n
            sigs.append(signature(img, layout) if img is not None and is_visible(img, layout) else None)
            if i % 100 == 0 or i == len(times):
                progress(f"  360p scan: {i}/{len(times)} samples")
    stats.samples = len(times)

    # 2. Group into scenes: a scoreboard change opens a new scene.
    scenes = group_scenes(times, sigs)
    progress(f"  {len(scenes)} scoreboard changes, reading at 720p")

    # 3. Read every scene at 720p.
    reader = Reader(layout)
    readings: list[tuple[Scene, Reading]] = []
    for scene in scenes:
        reading = _read_scene(video.high, reader, scene, stats)
        if reading:
            readings.append((scene, reading))

    matches = merge_readings(readings, lead=step)
    progress(f"  {len(matches)} matches found")
    index = VideoIndex(video.video_id, video.title, video.url, video.duration, matches)
    return index, stats


def group_scenes(times: list[int], sigs: list) -> list[Scene]:
    scenes: list[Scene] = []
    prev = None
    for t, sig in zip(times, sigs):
        if sig is None:
            prev = None
            continue
        if prev is not None and same_board(prev, sig) and scenes:
            scenes[-1].end = t
            scenes[-1].times.append(t)
        else:
            scenes.append(Scene(start=t, end=t, times=[t]))
        prev = sig
    return scenes


def _read_scene(stream: Stream, reader: Reader, scene: Scene, stats: Stats, tries: int = 3) -> Reading | None:
    """Read a scene; if the round is missing (the header sometimes shows the event name) try later frames."""
    best = None
    for t in scene.times[:tries]:
        img, n = stream.frame_at(t)
        stats.bytes += n
        stats.reads += 1
        reading = reader.read(img) if img is not None else None
        if reading:
            best = _combine(best, reading)
            if best.round and best.category:
                break
    return best


def _combine(a: Reading | None, b: Reading) -> Reading:
    if a is None:
        return b
    return Reading(
        category=a.category or b.category,
        round=a.round or b.round,
        white=a.white if a.white.club else b.white,
        blue=a.blue if a.blue.club else b.blue,
    )


def _key(name: str) -> str:
    return "".join(c for c in name.upper() if c.isalnum())


def merge_readings(readings: list[tuple[Scene, Reading]], lead: int) -> list[Match]:
    """Merge consecutive scenes with the same athletes (scoreboard hidden and shown again, graphics change)."""
    matches: list[Match] = []
    last_key = None
    for scene, r in readings:
        key = (_key(r.white.name), _key(r.blue.name))
        if matches and key == last_key:
            m = matches[-1]
            m.end = scene.end
            m.category = m.category or r.category
            m.round = m.round or r.round
            continue
        matches.append(Match(
            start=max(0, scene.start - lead),
            end=scene.end,
            category=r.category,
            round=r.round,
            white=r.white,
            blue=r.blue,
        ))
        last_key = key
    return matches


def _hms(s: int) -> str:
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"
