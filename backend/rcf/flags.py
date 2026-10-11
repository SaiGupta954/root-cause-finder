"""Simple, explainable rules that flag unusual pattern groups. No ML here on purpose."""

from __future__ import annotations

import math
import re
from datetime import datetime

from .grouping import PatternGroup

ERROR_WORDS_RE = re.compile(
    r"\b(error|errors|fail|failed|failure|failures|denied|timeout|timed out|refused|segfault|"
    r"out of memory|oom-killer|killed process|no space left|fatal|panic|"
    r"cannot|can't|couldn't|could not|unable to|not found|unreachable)(?!\w)",
    re.IGNORECASE,
)

SPIKE_FACTOR = 3.0  # a minute with more than 3x the normal rate is a spike
SPIKE_MIN_COUNT = 5  # ignore "spikes" of 1-4 lines
LATE_START_FRACTION = 0.5  # with no baseline, a pattern first seen in the 2nd half of the log counts as new
MIN_SCORE = 2.0  # groups below this are not reported as suspicious

WEIGHTS = {"error_words": 3.0, "new_pattern": 2.0, "spike": 2.0}
# A brand-new pattern made only of INFO lines (boot messages after a reboot, a new cron job) is weak
# evidence by itself. It still adds to the score but cannot reach MIN_SCORE alone.
NEW_INFO_ONLY_WEIGHT = 1.0


def error_words(group: PatternGroup) -> list[str]:
    return sorted({m.lower() for m in ERROR_WORDS_RE.findall(group.template)})


def is_new(group: PatternGroup, baseline_ids: set[int] | None,
           start: datetime | None, end: datetime | None) -> tuple[bool, str]:
    if baseline_ids is not None:
        return group.pattern_id not in baseline_ids, "never seen in the baseline log"
    if start and end and group.first_seen and end > start:
        cutoff = start + (end - start) * LATE_START_FRACTION
        return group.first_seen > cutoff, f"first appears late in the log ({group.first_seen:%b %d %H:%M:%S})"
    return False, ""


def spike(group: PatternGroup, active_minutes: int) -> tuple[bool, float, str]:
    """Normal rate = the group's lines spread evenly over the minutes in which the log wrote anything.

    Counting only active minutes keeps long quiet gaps (a log that covers six weeks) from making
    every ordinary burst look like a spike.
    """
    if not group.per_minute or active_minutes <= 0:
        return False, 0.0, ""
    normal_rate = group.count / active_minutes
    peak_minute, peak = max(group.per_minute.items(), key=lambda kv: kv[1])
    ratio = peak / normal_rate if normal_rate else 0.0
    hit = peak >= SPIKE_MIN_COUNT and ratio > SPIKE_FACTOR
    return hit, ratio, f"{peak} lines in the minute {peak_minute:%b %d %H:%M} ({ratio:.0f}x normal)"


def apply_flags(groups: dict[int, PatternGroup], start: datetime | None, end: datetime | None,
                baseline_ids: set[int] | None = None) -> list[PatternGroup]:
    """Flag each group and return the suspicious ones, most suspicious first."""
    active_minutes = len({m for g in groups.values() for m in g.per_minute})
    for g in groups.values():
        g.flags, g.reasons, g.score = [], [], 0.0

        words = error_words(g)
        if words:
            g.flags.append("error_words")
            g.reasons.append("error words: " + ", ".join(words))
            g.score += WEIGHTS["error_words"]

        new, why = is_new(g, baseline_ids, start, end)
        if new:
            g.flags.append("new_pattern")
            g.reasons.append(why)
            info_only = set(g.levels) <= {"INFO", "DEBUG"}
            g.score += NEW_INFO_ONLY_WEIGHT if info_only else WEIGHTS["new_pattern"]

        hit, ratio, why = spike(g, active_minutes)
        g.peak_ratio = ratio
        if hit:
            g.flags.append("spike")
            g.reasons.append(why)
            # Bigger spikes rank a little higher, but never outweigh a whole extra rule.
            g.score += WEIGHTS["spike"] + min(1.0, math.log10(ratio) / 3)

    flagged = [g for g in groups.values() if g.score >= MIN_SCORE]
    # Ties: earlier first appearance wins, since the first failure is usually closest to the root cause.
    flagged.sort(key=lambda g: (-g.score, g.first_seen or datetime.max, -g.count))
    return flagged
