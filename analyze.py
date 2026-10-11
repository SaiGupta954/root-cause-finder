"""Print the most suspicious error groups in a log file.

    python analyze.py data/Linux_2k.log
    python analyze.py broken.log --baseline normal.log --top 5
"""

from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from rcf import analyze_file  # noqa: E402


def format_lines(line_numbers: list[int], limit: int = 12) -> str:
    shown = ", ".join(str(n) for n in line_numbers[:limit])
    extra = len(line_numbers) - limit
    return shown + (f" ... (+{extra} more)" if extra > 0 else "")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Find the most suspicious error groups in a Linux log.")
    ap.add_argument("logfile")
    ap.add_argument("--baseline", help="a normal log; patterns missing from it are flagged as new")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--year", type=int, help="year for syslog timestamps, which have none (default: this year)")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.logfile):
        print(f"error: no such file: {args.logfile}", file=sys.stderr)
        return 2

    t0 = time.perf_counter()
    result = analyze_file(args.logfile, baseline_path=args.baseline, year=args.year)
    elapsed = time.perf_counter() - t0

    if not result.records:
        print("The file is empty or has no readable lines.")
        return 1

    span = f"{result.start:%b %d %H:%M:%S} -> {result.end:%b %d %H:%M:%S}" if result.start else "no timestamps"
    print(f"{args.logfile}: {len(result.records)} lines, {len(result.groups)} patterns, "
          f"{len(result.suspicious)} flagged ({span}, {elapsed:.1f}s)\n")

    for rank, g in enumerate(result.suspicious[: args.top], start=1):
        when = f"{g.first_seen:%b %d %H:%M:%S}" if g.first_seen else "?"
        print(f"#{rank}  score {g.score:.1f}  [{', '.join(g.flags)}]  count {g.count}  first seen {when}")
        print(f"    pattern: {g.template}")
        for reason in g.reasons:
            print(f"    - {reason}")
        print(f"    lines:   {format_lines(g.line_numbers)}")
        print(f"    example: {g.example.strip()[:160]}\n")

    if not result.suspicious:
        print("Nothing looks suspicious.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
