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
    ap.add_argument("--explain", action="store_true", help="also find the root cause with the KB and the LLM")
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
    if args.explain:
        print_root_cause(args.logfile)
    return 0


def print_root_cause(path: str) -> None:
    from rcf.pipeline import default_kb, default_llm, find_root_cause

    with open(path, encoding="utf-8", errors="replace") as fh:
        report = find_root_cause(fh.readlines(), default_kb(), default_llm())
    rc = report["root_cause"]
    print("=" * 70)
    print(f"ROOT CAUSE: {rc['root_cause']}")
    print(f"category: {rc['category']}  alternatives: {rc['alternatives']}  confidence: {rc['confidence']}")
    if rc.get("error"):
        print(f"note: {rc['error']}")
    print("evidence:")
    for ev in rc["evidence_lines"]:
        print(f"  L{ev['line']}: {ev['text'].strip()[:150]}")
    for d in rc.get("dropped_evidence", []):
        print(f"  dropped: {d['reason']}")
    print("next steps:")
    for step in rc["next_steps"]:
        print(f"  - {step}")
    print(f"({report['stats']['seconds']}s total, {report['stats'].get('llm_seconds', 0)}s in the LLM)")


if __name__ == "__main__":
    sys.exit(main())
