"""Turn raw log lines into structured records: timestamp, level, pattern ID and values.

Patterns come from Drain3. Many lines like
    "Failed password for root from 1.2.3.4 port 22 ssh2"
collapse into one pattern such as
    "sshd: Failed password for <*> from <IP> port <NUM> ssh2"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

from drain3 import TemplateMiner
from drain3.masking import MaskingInstruction
from drain3.template_miner_config import TemplateMinerConfig

# "Jun 14 15:16:01 combo sshd(pam_unix)[19939]: message"   (classic syslog, Loghub Linux/OpenSSH)
SYSLOG_RE = re.compile(
    r"^(?P<ts>[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"(?P<host>\S+)\s+"
    r"(?P<component>[^\s:\[]+(?:\([^)]*\))?)(?:\[(?P<pid>\d+)\])?:\s?"
    r"(?P<message>.*)$"
)
# "2026-10-11T10:00:00.123+00:00 host nginx[12]: message"  (journalctl -o short-iso, rsyslog ISO)
ISO_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?\s+"
    r"(?P<host>\S+)\s+"
    r"(?P<component>[^\s:\[]+(?:\([^)]*\))?)(?:\[(?P<pid>\d+)\])?:\s?"
    r"(?P<message>.*)$"
)
# An explicit level word near the start of the message, e.g. "ERROR: ..." or "[warn] ..."
EXPLICIT_LEVEL_RE = re.compile(
    r"^\W{0,2}(?P<level>emerg|alert|crit(?:ical)?|err(?:or)?|warn(?:ing)?|notice|info|debug)\b",
    re.IGNORECASE,
)
ERROR_HINT_RE = re.compile(
    r"\b(error|fail(?:ed|ure)?|denied|timed? ?out|refused|segfault|panic|fatal|"
    r"out of memory|oom|no space left|cannot|can't|unable)\b",
    re.IGNORECASE,
)
WARN_HINT_RE = re.compile(r"\b(warn(?:ing)?|deprecated|retry(?:ing)?)\b", re.IGNORECASE)

LEVEL_ALIASES = {
    "emerg": "CRITICAL", "alert": "CRITICAL", "crit": "CRITICAL", "critical": "CRITICAL",
    "err": "ERROR", "error": "ERROR",
    "warn": "WARNING", "warning": "WARNING",
    "notice": "INFO", "info": "INFO", "debug": "DEBUG",
}

MASKS = [
    MaskingInstruction(r"(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?", "IP"),
    MaskingInstruction(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", "MAC"),
    MaskingInstruction(r"0x[0-9a-fA-F]+", "HEX"),
    MaskingInstruction(r"(?<![\w/])(?:/[\w.\-]+)+/?", "PATH"),
    MaskingInstruction(r"(?<![\w.])[-+]?\d+(?:\.\d+)?(?![\w.])", "NUM"),
]


@dataclass
class LogRecord:
    line_no: int  # 1-based, matches the line number in the original file
    raw: str
    timestamp: datetime | None
    host: str | None
    component: str | None
    level: str
    message: str
    pattern_id: int = 0
    values: list[str] = field(default_factory=list)


def _parse_timestamp(text: str, year: int) -> datetime | None:
    text = re.sub(r"\s+", " ", text)
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    try:
        # Syslog has no year; supply one so dates sort correctly.
        return datetime.strptime(f"{year} {text}", "%Y %b %d %H:%M:%S")
    except ValueError:
        return None


def infer_level(message: str) -> str:
    m = EXPLICIT_LEVEL_RE.match(message)
    if m:
        return LEVEL_ALIASES[m.group("level").lower()]
    if ERROR_HINT_RE.search(message):
        return "ERROR"
    if WARN_HINT_RE.search(message):
        return "WARNING"
    return "INFO"


def split_line(raw: str, line_no: int, year: int) -> LogRecord:
    """Split one line into header fields and message. Lines with no known header keep the whole text."""
    for regex in (SYSLOG_RE, ISO_RE):
        m = regex.match(raw)
        if m:
            component = re.sub(r"\[\d+\]$", "", m.group("component"))
            message = m.group("message").strip()
            return LogRecord(
                line_no=line_no,
                raw=raw,
                timestamp=_parse_timestamp(m.group("ts"), year),
                host=m.group("host"),
                component=component,
                level=infer_level(message),
                message=message,
            )
    message = raw.strip()
    return LogRecord(line_no, raw, None, None, None, infer_level(message), message)


def new_template_miner() -> TemplateMiner:
    config = TemplateMinerConfig()
    config.masking_instructions = list(MASKS)
    config.drain_sim_th = 0.4
    config.drain_depth = 4
    config.profiling_enabled = False
    return TemplateMiner(config=config)


class LogParser:
    """Holds one Drain3 miner so a baseline log and a target log share pattern IDs."""

    def __init__(self, year: int | None = None):
        self.miner = new_template_miner()
        self.year = year or datetime.now().year

    @staticmethod
    def _drain_input(rec: LogRecord) -> str:
        # The level goes first so Drain can never merge "Failed password ..." with "Accepted password ...";
        # without it, both become "<*> password ..." and the error word is lost. The component keeps
        # "sshd: X" and "cron: X" apart. PIDs are already dropped. template() strips the level again.
        body = f"{rec.component}: {rec.message}" if rec.component else rec.message
        return f"{rec.level} {body}"

    def parse_lines(self, lines: Iterable[str]) -> list[LogRecord]:
        records: list[LogRecord] = []
        year = self.year
        prev_month = None
        for i, raw in enumerate(lines, start=1):
            raw = raw.rstrip("\r\n")
            if not raw.strip():
                continue
            rec = split_line(raw, i, year)
            # Syslog has no year: when the month goes backwards (Dec -> Jan), roll the year forward.
            if rec.timestamp and SYSLOG_RE.match(raw):
                if prev_month and rec.timestamp.month < prev_month:
                    year += 1
                    rec.timestamp = rec.timestamp.replace(year=year)
                prev_month = rec.timestamp.month
            result = self.miner.add_log_message(self._drain_input(rec))
            rec.pattern_id = result["cluster_id"]
            records.append(rec)

        # Drain templates keep generalising as lines arrive, so extract values only once all lines are in.
        for rec in records:
            template = self.raw_template(rec.pattern_id)
            rec.values = self.miner.get_parameter_list(template, self._drain_input(rec))
        return records

    def parse_file(self, path: str) -> list[LogRecord]:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return self.parse_lines(fh)

    def raw_template(self, pattern_id: int) -> str:
        return self.miner.drain.id_to_cluster[pattern_id].get_template()

    def template(self, pattern_id: int) -> str:
        """The pattern as people should see it, without the level token added for Drain."""
        return self.raw_template(pattern_id).split(" ", 1)[-1]
