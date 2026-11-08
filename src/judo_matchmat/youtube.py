"""Frame access for YouTube videos without downloading them.

YouTube also serves every video as an HLS playlist: segments a few seconds long, each with
its own URL. A segment URL carries a ``slices`` parameter with the byte range of the source
file; shortening it downloads only the beginning of the segment, which already contains the
first full frame (keyframe).
"""

from __future__ import annotations

import bisect
import re
import subprocess
from dataclasses import dataclass

import cv2
import imageio_ffmpeg
import numpy as np
import requests
import yt_dlp

# Video-only HLS itags, in order of preference.
LOW_ITAGS = ("230", "605")  # 360p
HIGH_ITAGS = ("232", "311", "609")  # 720p

_SLICES = re.compile(r"slices%3D(\d+)-(\d+),(\d+)-(\d+)")
_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


class YouTubeError(RuntimeError):
    pass


@dataclass
class Stream:
    """HLS playlist for one resolution: segment URLs and their start times."""

    segments: list[str]
    starts: list[float]
    headers: dict[str, str]
    first_bytes: int  # bytes that usually suffice to decode the first frame

    def segment_at(self, t: float) -> int:
        return max(0, bisect.bisect_right(self.starts, t) - 1)

    def frame_at(self, t: float) -> tuple[np.ndarray | None, int]:
        """First frame of the segment containing ``t``. Returns (image, bytes downloaded)."""
        url = self.segments[self.segment_at(t)]
        m = _SLICES.search(url)
        attempts = [self.first_bytes, self.first_bytes * 3, None] if m else [None]
        downloaded = 0
        for size in attempts:
            target = url
            if size is not None:
                end = min(int(m[4]), int(m[3]) + size - 1)
                target = url.replace(m[0], f"slices%3D{m[1]}-{m[2]},{m[3]}-{end}")
            body = _get(target, self.headers)
            downloaded += len(body)
            img, clean = _decode_first_frame(body)
            # A truncated frame decodes with errors: retry with a larger download.
            if img is not None and (clean or size is None):
                return img, downloaded
        return None, downloaded


@dataclass
class Video:
    video_id: str
    title: str
    url: str
    duration: int
    low: Stream
    high: Stream


def open_video(url: str) -> Video:
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "noprogress": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        raise YouTubeError(f"Cannot read the video: {e}") from e

    formats = {f["format_id"]: f for f in info.get("formats", [])}
    low = _pick(formats, LOW_ITAGS, first_bytes=60_000)
    high = _pick(formats, HIGH_ITAGS, first_bytes=150_000)
    if low is None or high is None:
        raise YouTubeError("YouTube does not offer 360p and 720p HLS streams for this video.")
    return Video(
        video_id=info["id"],
        title=info.get("title") or info["id"],
        url=info.get("webpage_url") or url,
        duration=int(info.get("duration") or 0),
        low=low,
        high=high,
    )


def _pick(formats: dict, itags: tuple[str, ...], first_bytes: int) -> Stream | None:
    for itag in itags:
        fmt = formats.get(itag)
        if fmt:
            headers = fmt.get("http_headers") or {}
            segments, starts = parse_playlist(_get(fmt["url"], headers).decode())
            if segments:
                return Stream(segments, starts, headers, first_bytes)
    return None


def parse_playlist(text: str) -> tuple[list[str], list[float]]:
    """Parse an HLS playlist into segment URLs and the start second of each one."""
    segments, starts = [], []
    t, duration = 0.0, 0.0
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#EXTINF:"):
            duration = float(line[8:].split(",")[0])
        elif line and not line.startswith("#"):
            segments.append(line)
            starts.append(t)
            t += duration
    return segments, starts


def _get(url: str, headers: dict[str, str]) -> bytes:
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.content


def _decode_first_frame(data: bytes) -> tuple[np.ndarray | None, bool]:
    """Decode the first frame. The flag is False when ffmpeg reported errors."""
    if not data:
        return None, False
    p = subprocess.run(
        [_FFMPEG, "-loglevel", "error", "-f", "mpegts", "-i", "pipe:0",
         "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "pipe:1"],
        input=data, capture_output=True,
    )
    if not p.stdout:
        return None, False
    img = cv2.imdecode(np.frombuffer(p.stdout, np.uint8), cv2.IMREAD_COLOR)
    return img, not p.stderr.strip()
