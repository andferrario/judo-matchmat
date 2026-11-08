"""Find the matches in YouTube videos of judo tournaments by reading the on-screen scoreboard."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import __version__, report
from .pipeline import scan
from .scoreboard import LAYOUTS
from .youtube import YouTubeError


def _seconds(value: str) -> int:
    """'1:05:00', '65:00' or '3900' → seconds."""
    total = 0
    for part in value.split(":"):
        total = total * 60 + int(part)
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="matchmat", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="scan one or more videos and update the results page")
    p_scan.add_argument("urls", nargs="+", metavar="URL", help="YouTube video links")
    p_scan.add_argument("-o", "--out", type=Path, default=Path("results"), help="results folder (default: results)")
    p_scan.add_argument("--layout", choices=sorted(LAYOUTS), default="fijlkam", help="scoreboard graphics")
    p_scan.add_argument("--step", type=int, default=15, help="seconds between samples (default: 15)")
    p_scan.add_argument("--from", dest="start", type=_seconds, default=0, help="start time, e.g. 1:00:00")
    p_scan.add_argument("--to", dest="end", type=_seconds, default=None, help="end time, e.g. 2:00:00")
    p_scan.add_argument("--title", default="Matches", help="title of the results page")

    p_report = sub.add_parser("report", help="rebuild the results page from saved scans")
    p_report.add_argument("out", nargs="?", type=Path, default=Path("results"))
    p_report.add_argument("--title", default="Matches")

    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    if args.command == "scan":
        failed = 0
        for url in args.urls:
            t0 = time.time()
            try:
                index, stats = scan(url, LAYOUTS[args.layout], step=args.step,
                                    start=args.start, end=args.end, progress=print)
            except YouTubeError as e:
                print(f"Error: {e}", file=sys.stderr)
                failed += 1
                continue
            path = args.out / f"{index.video_id}.json"
            index.save(path)
            print(f"  saved {path} ({stats.bytes / 1e6:.0f} MB downloaded in {time.time() - t0:.0f}s)\n")
        page = report.write(args.out, args.title)
        print(f"Results: {page.resolve()}")
        return 1 if failed else 0

    page = report.write(args.out, args.title)
    print(f"Results: {page.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
