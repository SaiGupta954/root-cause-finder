"""Check the LLM's answer with plain code. No AI here: evidence must point at real lines with real text."""

from __future__ import annotations

import re

MIN_QUOTE_CHARS = 8  # a quote shorter than this proves nothing ("error", "failed")
NOT_SURE = "not sure"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def check_evidence(item: object, by_line: dict[int, str]) -> tuple[bool, str]:
    """Return (ok, reason). The quote must be on the cited line: equal to it, or a long enough part of it."""
    if not isinstance(item, dict):
        return False, "not an object"
    try:
        line = int(item.get("line"))
    except (TypeError, ValueError):
        return False, "line number is not a number"
    if line not in by_line:
        return False, f"line {line} does not exist in the file"
    quote, actual = _norm(item.get("text", "")), _norm(by_line[line])
    if len(quote) < MIN_QUOTE_CHARS:
        return False, "quoted text is too short to check"
    if quote not in actual:
        return False, f"quoted text does not match line {line}"
    return True, "ok"


def verify_answer(answer: dict, by_line: dict[int, str], known_categories: set[str]) -> dict:
    """Keep only evidence that holds up. With no evidence left, the answer becomes "not sure"."""
    kept, dropped = [], []
    seen = set()
    for item in answer.get("evidence_lines") or []:
        ok, reason = check_evidence(item, by_line)
        if ok and int(item["line"]) not in seen:
            seen.add(int(item["line"]))
            # Show the real line from the file, not the model's copy of it.
            kept.append({"line": int(item["line"]), "text": by_line[int(item["line"])]})
        elif not ok:
            dropped.append({"item": item, "reason": reason})

    total = len(kept) + len(dropped)
    category = answer.get("category") if answer.get("category") in known_categories else "other"
    alternatives = [a for a in (answer.get("alternatives") or [])
                    if a in known_categories and a != category][:2]
    try:
        confidence = min(1.0, max(0.0, float(answer.get("confidence", 0))))
    except (TypeError, ValueError):
        confidence = 0.0

    if not kept:
        return {
            "status": "not_sure",
            "root_cause": NOT_SURE,
            "category": "unknown",
            "alternatives": [],
            "confidence": 0.0,
            "evidence_lines": [],
            "dropped_evidence": dropped,
            "next_steps": [],
            "unverified_guess": answer.get("root_cause"),
        }
    return {
        "status": "verified",
        "root_cause": str(answer.get("root_cause", "")).strip() or NOT_SURE,
        "category": category,
        "alternatives": alternatives,
        # Trust drops with every piece of evidence that failed the check.
        "confidence": round(confidence * len(kept) / total, 2),
        "evidence_lines": kept,
        "dropped_evidence": dropped,
        "next_steps": [str(s) for s in (answer.get("next_steps") or [])][:6],
    }
