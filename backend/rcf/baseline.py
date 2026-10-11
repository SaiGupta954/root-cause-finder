"""Keyword-rules-only baseline (no LLM, no vector search), used to measure what the AI adds.

Each failure type has a few hand-written regexes. Count matching lines per type; the type with the most
matching lines wins. Ties go to the type whose first match comes earliest.
"""

from __future__ import annotations

import re

from .parser import LogRecord

RULES: dict[str, list[str]] = {
    "disk_full": [r"no space left on device", r"\bENOSPC\b", r"disk (is )?full", r"filesystem full"],
    "dns_failure": [r"temporary failure in name resolution", r"name or service not known",
                    r"could not resolve", r"no servers could be reached", r"\bEAI_AGAIN\b", r"\bNXDOMAIN\b"],
    "crash_loop": [r"restart counter is at", r"start request repeated too quickly", r"exited, code=exited",
                   r"back-off restarting", r"\bexited with code\b"],
    "permission_denied": [r"permission denied", r"operation not permitted", r"\bEACCES\b"],
    "port_in_use": [r"address already in use", r"\bEADDRINUSE\b", r"port is already allocated",
                    r"could not bind", r"bind\(\) to .* failed"],
    "out_of_memory": [r"out of memory", r"cannot allocate memory", r"oom[-_ ]?kill", r"\bMemoryError\b",
                      r"\bENOMEM\b", r"\bKilled\b"],
    "bad_config": [r"syntax error", r"unknown directive", r"bad configuration option", r"parse error",
                   r"configuration file .* test failed", r"invalid (config|configuration|value)"],
    "ssh_bruteforce": [r"failed password for", r"invalid user", r"authentication failure",
                       r"too many authentication failures"],
}
COMPILED = {cat: re.compile("|".join(pats), re.IGNORECASE) for cat, pats in RULES.items()}


def keyword_rank(records: list[LogRecord]) -> list[dict]:
    """Return failure types ranked by matching line count, with the matching line numbers."""
    hits: dict[str, list[int]] = {}
    for rec in records:
        for cat, rx in COMPILED.items():
            if rx.search(rec.raw):
                hits.setdefault(cat, []).append(rec.line_no)
    ranked = sorted(hits.items(), key=lambda kv: (-len(kv[1]), kv[1][0]))
    return [{"category": cat, "count": len(lines), "lines": lines} for cat, lines in ranked]
