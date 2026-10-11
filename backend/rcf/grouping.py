"""Group parsed records by pattern: count, first/last seen, and count per minute."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from .parser import LogParser, LogRecord


@dataclass
class PatternGroup:
    pattern_id: int
    template: str
    count: int = 0
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    first_line: int = 0
    line_numbers: list[int] = field(default_factory=list)
    levels: Counter = field(default_factory=Counter)
    per_minute: Counter = field(default_factory=Counter)  # minute (datetime) -> count
    example: str = ""
    # Filled in by flags.py
    flags: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    score: float = 0.0
    peak_ratio: float = 0.0


def minute_of(ts: datetime) -> datetime:
    return ts.replace(second=0, microsecond=0)


def group_records(records: list[LogRecord], parser: LogParser) -> dict[int, PatternGroup]:
    groups: dict[int, PatternGroup] = {}
    for rec in records:
        g = groups.get(rec.pattern_id)
        if g is None:
            g = groups[rec.pattern_id] = PatternGroup(
                pattern_id=rec.pattern_id,
                template=parser.template(rec.pattern_id),
                first_line=rec.line_no,
                example=rec.raw,
            )
        g.count += 1
        g.line_numbers.append(rec.line_no)
        g.levels[rec.level] += 1
        if rec.timestamp:
            if g.first_seen is None or rec.timestamp < g.first_seen:
                g.first_seen = rec.timestamp
            if g.last_seen is None or rec.timestamp > g.last_seen:
                g.last_seen = rec.timestamp
            g.per_minute[minute_of(rec.timestamp)] += 1
    return groups


def time_span(records: list[LogRecord]) -> tuple[datetime | None, datetime | None]:
    stamps = [r.timestamp for r in records if r.timestamp]
    if not stamps:
        return None, None
    return min(stamps), max(stamps)
