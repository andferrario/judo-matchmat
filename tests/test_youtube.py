from judo_matchmat.youtube import Stream, parse_playlist


def test_parse_playlist_accumulates_start_times():
    text = "#EXTM3U\n#EXTINF:6.0,\nhttps://a/1\n#EXTINF:6.0,\nhttps://a/2\n#EXTINF:4.5,\nhttps://a/3\n#EXT-X-ENDLIST"
    segments, starts = parse_playlist(text)
    assert segments == ["https://a/1", "https://a/2", "https://a/3"]
    assert starts == [0.0, 6.0, 12.0]


def test_segment_at_finds_containing_segment():
    stream = Stream(segments=["a", "b", "c"], starts=[0.0, 6.0, 12.0], headers={}, first_bytes=1)
    assert [stream.segment_at(t) for t in (0, 5.9, 6, 13, 999)] == [0, 0, 1, 2, 2]
