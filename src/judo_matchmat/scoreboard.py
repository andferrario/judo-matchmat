"""On-screen scoreboard detection and reading."""

from __future__ import annotations

import re
from dataclasses import dataclass

import cv2
import numpy as np

from .models import Athlete

Rect = tuple[float, float, float, float]  # x0, y0, x1, y1 as fractions of the frame


@dataclass(frozen=True)
class Layout:
    """Where the scoreboard sits in the frame. It varies between broadcast graphics providers."""

    name: str
    board: Rect  # whole scoreboard, read with OCR
    names: Rect  # category and athlete rows without clock and scores: changes only between matches
    white_row: Rect  # white background of the first athlete's row: tells whether the scoreboard is shown
    white_threshold: float = 190.0


LAYOUTS = {
    # FIJLKAM TV live streams (e.g. Campionato Italiano Assoluto A2 2026).
    "fijlkam": Layout(
        name="fijlkam",
        board=(0.72, 0.84, 1.00, 0.99),
        names=(0.72, 0.84, 0.93, 0.98),
        white_row=(0.73, 0.89, 0.92, 0.92),
    ),
}


def crop(img: np.ndarray, rect: Rect) -> np.ndarray:
    h, w = img.shape[:2]
    return img[int(h * rect[1]):int(h * rect[3]), int(w * rect[0]):int(w * rect[2])]


def is_visible(img: np.ndarray, layout: Layout) -> bool:
    """The first athlete's row is white: bright and colourless (the yellow mat is bright but saturated)."""
    hsv = cv2.cvtColor(crop(img, layout.white_row), cv2.COLOR_BGR2HSV)
    return float(hsv[..., 2].mean()) > layout.white_threshold and float(hsv[..., 1].mean()) < 40


def signature(img: np.ndarray, layout: Layout) -> np.ndarray:
    """Fingerprint of the names area, at a fixed size so different resolutions compare."""
    gray = cv2.cvtColor(crop(img, layout.names), cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, (160, 40), interpolation=cv2.INTER_AREA).astype(np.float32)


def same_board(a: np.ndarray, b: np.ndarray, threshold: float = 12.0) -> bool:
    return float(np.abs(a - b).mean()) <= threshold


@dataclass
class Reading:
    category: str
    round: str
    white: Athlete
    blue: Athlete


@dataclass
class TextBox:
    text: str
    score: float
    x: float  # left edge
    y: float  # vertical centre
    height: float


_CATEGORY = re.compile(r"^([+-]?)\s*(\d{2,3})\s*kg$", re.IGNORECASE)
_CLOCK = re.compile(r"^\d{1,2}:\d{2}$")
# English and Italian round names.
_ROUND = re.compile(
    r"round|pool|final|semi|quarter|repech|bronze|gold|repescag|recuper|finale|turno", re.IGNORECASE
)
_CLUB_CODE = re.compile(r"^[0-9A-Z]{6,10}\s*-\s*(.+)$", re.IGNORECASE)


def _fix_zeros(text: str) -> str:
    """OCR mixes up O and 0: a 0 next to letters and not to other digits is an O ('JUD0' → 'JUDO')."""
    return re.sub(r"(?<=[A-Z])0(?!\d)|(?<!\d)0(?=[A-Z])", "O", text)


def normalize_name(text: str) -> str:
    """'j.ROSSI' → 'J. ROSSI'."""
    text = _fix_zeros(re.sub(r"\s+", " ", text).strip().upper())
    return re.sub(r"^(\w)\.\s*", r"\1. ", text)


def normalize_club(text: str) -> str:
    """Strip the leading club code: '19ME0266-JUDO CLUB' → 'JUDO CLUB'."""
    text = re.sub(r"\s+", " ", text).strip()
    m = _CLUB_CODE.match(text)
    return _fix_zeros((m[1] if m else text).strip().upper())


def normalize_category(text: str) -> str:
    m = _CATEGORY.match(text.strip())
    if not m:
        return ""
    sign = m[1] or "-"  # OCR often drops the minus in front of the weight
    return f"{sign}{m[2]} kg"


def parse_board(boxes: list[TextBox], min_score: float = 0.5) -> Reading | None:
    """Rebuild the scoreboard from the position of the text.

    Row 1: category, round, clock. Row 2: white athlete and club. Row 3: blue athlete and club.
    """
    boxes = sorted((b for b in boxes if b.score >= min_score and b.text.strip()), key=lambda b: b.y)
    if not boxes:
        return None
    tolerance = float(np.median([b.height for b in boxes])) * 0.6
    rows: list[list[TextBox]] = []
    for b in boxes:
        if rows and abs(rows[-1][-1].y - b.y) <= tolerance:
            rows[-1].append(b)
        else:
            rows.append([b])
    if len(rows) < 3:
        return None
    header, white, blue = (sorted(r, key=lambda b: b.x) for r in rows[-3:])

    category, round_ = "", ""
    for b in header:
        if not category and normalize_category(b.text):
            category = normalize_category(b.text)
        elif _ROUND.search(b.text) and not _CLOCK.match(b.text.strip()):
            round_ = re.sub(r"\s+", " ", b.text).strip()

    athletes = [_athlete(white), _athlete(blue)]
    if not all(a and a.name for a in athletes):
        return None
    return Reading(category=category, round=round_, white=athletes[0], blue=athletes[1])


def _athlete(row: list[TextBox]) -> Athlete | None:
    texts = [b.text for b in row if not b.text.strip().isdigit()]
    if not texts or len(re.sub(r"[^A-Za-zÀ-ÿ]", "", texts[0])) < 3:
        return None
    return Athlete(name=normalize_name(texts[0]), club=normalize_club(texts[1]) if len(texts) > 1 else "")


class Reader:
    """Scoreboard OCR. The model is loaded on the first read."""

    def __init__(self, layout: Layout):
        self.layout = layout
        self._engine = None

    def read(self, img: np.ndarray) -> Reading | None:
        if self._engine is None:
            from rapidocr import RapidOCR

            self._engine = RapidOCR()
        result = self._engine(crop(img, self.layout.board))
        if result.boxes is None:
            return None
        boxes = []
        for pts, text, score in zip(result.boxes, result.txts, result.scores):
            ys = [p[1] for p in pts]
            boxes.append(TextBox(text=text, score=float(score), x=float(min(p[0] for p in pts)),
                                 y=float(np.mean(ys)), height=float(max(ys) - min(ys))))
        return parse_board(boxes)
