# judo-matchmat

**Find any bout in hours of judo tournament footage.**

Tournament live streams on YouTube are often one 5–6 hour video per mat, with no chapters. Finding a specific athlete means scrubbing back and forth at random. `judo-matchmat` reads the scoreboard shown on screen (names, clubs, weight category and round) and builds a searchable page of every match, each with a link that opens the video at the right moment.

```
$ matchmat scan "https://www.youtube.com/watch?v=…" --title "National Championship 2026"
National Championship 2026 – Day 2 – Mat 3 (5:29:49)
  360p scan: 1320/1320 samples
  114 scoreboard changes, reading at 720p
  40 matches found
  saved results/VIDEO_ID.json (106 MB downloaded in 445s)

Results: results/index.html
```

The results page lists the matches per video and filters them as you type:

```
1:01:30   M. ROSSI  JUDO CLUB ROMA   vs   L. BIANCHI  DOJO EQUIPE    Watch ▶
          -63 kg · Seniors - Female - Repechage
```

## How it works

The video is **never downloaded**. YouTube serves every video as an HLS playlist of short segments, and each segment URL carries the byte range it maps to. Shortening that range fetches just the first frame of a segment, about 40 KB at 360p.

1. **Light pass at 360p.** One frame every 15 seconds. For each one, check whether the scoreboard is on screen and whether it changed since the previous sample. Clock and scores are ignored, so only a new match counts as a change.
2. **Read at 720p.** Only where the scoreboard changed, fetch a sharper frame and run OCR ([RapidOCR](https://github.com/RapidAI/RapidOCR), on-device).
3. **Parse by position.** The scoreboard has a fixed structure: the top row holds category and round, the next two rows hold each athlete and their club. Text is assigned by row, not guessed from keywords.
4. **Merge.** Consecutive readings with the same two athletes become one match.

On a 5.5-hour mat video this takes about 7 minutes and roughly 100 MB of traffic.

## Install

You need [uv](https://docs.astral.sh/uv/). Everything else (Python packages, ffmpeg, OCR models) is installed inside the project folder.

```bash
git clone https://github.com/andferrario/judo-matchmat.git
cd judo-matchmat
uv sync
```

The uv cache is configured to live in `.tools/cache`. If uv also needs to download Python and you want that inside the project too, run the first install as:

```bash
UV_PYTHON_INSTALL_DIR=.tools/python uv sync
```

To uninstall, delete the folder.

## Usage

Scan one or more videos (typically one per mat):

```bash
uv run matchmat scan "https://www.youtube.com/watch?v=MAT_1" "https://www.youtube.com/watch?v=MAT_2" --title "National Championship 2026"
```

Results go to `results/`: one JSON file per video plus `results/index.html`, the page to open in a browser. Every new scan is added to the same page. Click an athlete's name to see all of their matches.

| Option | Meaning |
|---|---|
| `--step 15` | seconds between samples |
| `--from 1:00:00 --to 2:00:00` | scan only part of a video |
| `--layout fijlkam` | scoreboard graphics (see below) |
| `-o DIR` | results folder (default `results`) |
| `--title TEXT` | title of the results page |

Rebuild the page from the saved JSON files without scanning again:

```bash
uv run matchmat report
```

## Supported scoreboards

Each broadcast provider puts its scoreboard somewhere else, so the screen areas are defined per layout in [`scoreboard.py`](src/judo_matchmat/scoreboard.py):

| Layout | Broadcast |
|---|---|
| `fijlkam` | FIJLKAM TV (Italian Judo Federation) live streams, scoreboard in the bottom-right corner |

Adding a layout means adding an entry to `LAYOUTS` with the fractions of the frame that hold the whole scoreboard, the names area and the first athlete's (white) row. Contributions for other federations and tournaments are welcome.

## Known limitations

- A match shown for less than one sampling interval can be missed (for example an ippon in the first seconds). Use `--step 10` to reduce the risk.
- Names and clubs are what OCR reads: expect occasional small typos, mostly in club names.
- It relies on YouTube serving the video as HLS, which is the case for public videos today. If YouTube changes that, the frame access in [`youtube.py`](src/judo_matchmat/youtube.py) needs updating.

## Development

```bash
uv run pytest
```

The code lives in `src/judo_matchmat/`:

| Module | Role |
|---|---|
| `youtube.py` | resolve the HLS playlists and fetch single frames |
| `scoreboard.py` | detect, fingerprint and read the scoreboard |
| `pipeline.py` | scan → scenes → readings → matches |
| `report.py` | self-contained HTML results page |
| `cli.py` | `matchmat scan` and `matchmat report` |

## Note

This tool does not re-host or store videos: it reads a few frames to build an index of links back to the original video on YouTube.

## License

[MIT](LICENSE)
