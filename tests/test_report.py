from judo_matchmat.models import Athlete, Match, VideoIndex
from judo_matchmat.report import build, write


def sample_index():
    m = Match(85, 300, "-63 kg", "Semi-final", Athlete("C. NERI", "JUDO CLUB"), Athlete("V. GIALLI"))
    return VideoIndex("abc123", "Mat 3", "https://youtu.be/abc123", 19789, [m])


def test_index_roundtrip(tmp_path):
    v = sample_index()
    v.save(tmp_path / "abc123.json")
    loaded = VideoIndex.load(tmp_path / "abc123.json")
    assert loaded == v
    assert loaded.link(loaded.matches[0]) == "https://www.youtube.com/watch?v=abc123&t=85s"


def test_report_embeds_data_safely(tmp_path):
    v = sample_index()
    v.matches[0].white.club = "</script><b>x"
    page = build([v], title="Test <cup>")
    assert "C. NERI" in page
    assert "<title>Test &lt;cup&gt;</title>" in page
    assert "</script><b>" not in page  # the payload cannot close the script tag

    v.save(tmp_path / "abc123.json")
    assert write(tmp_path).name == "index.html"
