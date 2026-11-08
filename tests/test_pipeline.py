import numpy as np

from judo_matchmat.models import Athlete
from judo_matchmat.pipeline import Scene, group_scenes, merge_readings
from judo_matchmat.scoreboard import Reading

A = np.zeros((40, 160), np.float32)
B = np.full((40, 160), 200, np.float32)


def reading(white, blue, round_=""):
    return Reading("-63 kg", round_, Athlete(white), Athlete(blue))


def test_group_scenes_splits_on_change_and_gap():
    times = [0, 15, 30, 45, 60, 75]
    sigs = [A, A, B, None, B, B]
    scenes = group_scenes(times, sigs)
    assert [(s.start, s.end) for s in scenes] == [(0, 15), (30, 30), (60, 75)]


def test_merge_readings_joins_same_athletes_and_fills_round():
    readings = [
        (Scene(100, 130), reading("C.NERI", "V. GIALLI")),
        (Scene(145, 300), reading("C. NERI", "V. GIALLI", "Semi-final")),
        (Scene(400, 600), reading("F. BRUNI", "A. FERRI")),
    ]
    matches = merge_readings(readings, lead=15)
    assert len(matches) == 2
    assert (matches[0].start, matches[0].end, matches[0].round) == (85, 300, "Semi-final")
    assert matches[1].white.name == "F. BRUNI"


def test_merge_readings_keeps_rematch_after_other_match():
    readings = [
        (Scene(0, 100), reading("C. NERI", "V. GIALLI")),
        (Scene(200, 300), reading("F. BRUNI", "A. FERRI")),
        (Scene(400, 500), reading("C. NERI", "V. GIALLI")),
    ]
    assert len(merge_readings(readings, lead=15)) == 3
