"""Root Cause Finder: find the most likely root cause in a Linux log, with the log lines as proof."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .flags import apply_flags
from .grouping import PatternGroup, group_records, time_span
from .parser import LogParser, LogRecord


@dataclass
class Analysis:
    records: list[LogRecord]
    groups: dict[int, PatternGroup]
    suspicious: list[PatternGroup]
    start: datetime | None
    end: datetime | None


def analyze_file(path: str, baseline_path: str | None = None, year: int | None = None) -> Analysis:
    parser = LogParser(year=year)
    baseline_ids = None
    if baseline_path:
        # Feed the normal log first, into the same miner, so its patterns get the same IDs.
        baseline_ids = {r.pattern_id for r in parser.parse_file(baseline_path)}
    records = parser.parse_file(path)
    groups = group_records(records, parser)
    start, end = time_span(records)
    suspicious = apply_flags(groups, start, end, baseline_ids)
    return Analysis(records, groups, suspicious, start, end)
