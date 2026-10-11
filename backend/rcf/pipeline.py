"""The whole pipeline: parse -> group -> flag -> search past fixes -> LLM -> check. Returns a JSON-ready report."""

from __future__ import annotations

import time
from collections import Counter

from . import analyze_lines
from .baseline import keyword_rank
from .grouping import PatternGroup, minute_of
from .kb import KnowledgeBase
from .llm import LLMClient, MAX_GROUPS, OllamaClient, answer_schema, build_prompt, parse_answer, SYSTEM_PROMPT
from .verify import NOT_SURE, verify_answer

TOP_GROUPS_IN_REPORT = 15
# An alternative category is shown only if its card matched the log nearly as well as the chosen one.
ALTERNATIVE_MIN_RATIO = 0.8
ERROR_LEVELS = {"ERROR", "CRITICAL"}


def group_to_dict(g: PatternGroup) -> dict:
    return {
        "pattern_id": g.pattern_id,
        "template": g.template,
        "count": g.count,
        "first_seen": g.first_seen.isoformat() if g.first_seen else None,
        "last_seen": g.last_seen.isoformat() if g.last_seen else None,
        "flags": g.flags,
        "reasons": g.reasons,
        "score": round(g.score, 2),
        "line_numbers": g.line_numbers[:50],
        "example": g.example.strip(),
    }


def timeline(analysis) -> list[dict]:
    """Errors and total lines per minute, for the chart."""
    total, errors = Counter(), Counter()
    for r in analysis.records:
        if r.timestamp:
            m = minute_of(r.timestamp)
            total[m] += 1
            if r.level in ERROR_LEVELS:
                errors[m] += 1
    return [{"minute": m.isoformat(), "lines": total[m], "errors": errors[m]} for m in sorted(total)]


def close_alternatives(category: str, alternatives: list[str], similarity: dict[str, float]) -> list[str]:
    """Keep only alternatives whose KB card scored within ALTERNATIVE_MIN_RATIO of the chosen category's card."""
    if not similarity:
        return []
    base = similarity.get(category, max(similarity.values()))
    return [a for a in alternatives if a in similarity and similarity[a] >= ALTERNATIVE_MIN_RATIO * base]


def apply_kb(rc: dict, kb: KnowledgeBase, similarity: dict[str, float]) -> dict:
    """Plain-code clean-up after the evidence check: honest alternatives, and fix steps from the KB only."""
    if rc["status"] != "verified":
        return rc
    rc["alternatives"] = close_alternatives(rc["category"], rc["alternatives"], similarity)
    card = kb.cards.get(rc["category"])
    rc["next_steps"] = card.fix_steps if card else []
    rc["next_steps_source"] = card.id if card else None
    return rc


def not_sure(reason: str) -> dict:
    return {"status": "not_sure", "root_cause": NOT_SURE, "category": "unknown", "alternatives": [],
            "confidence": 0.0, "evidence_lines": [], "dropped_evidence": [], "next_steps": [], "error": reason}


def find_root_cause(lines: list[str], kb: KnowledgeBase | None, llm: LLMClient | None,
                    use_llm: bool = True) -> dict:
    t0 = time.perf_counter()
    analysis = analyze_lines(lines)
    by_line = {r.line_no: r.raw for r in analysis.records}
    suspicious = analysis.suspicious

    report = {
        "stats": {
            "lines": len(analysis.records),
            "patterns": len(analysis.groups),
            "flagged": len(suspicious),
            "start": analysis.start.isoformat() if analysis.start else None,
            "end": analysis.end.isoformat() if analysis.end else None,
        },
        "timeline": timeline(analysis),
        "top_groups": [group_to_dict(g) for g in suspicious[:TOP_GROUPS_IN_REPORT]],
        "keyword_baseline": [{k: v for k, v in r.items() if k != "lines"} | {"lines": r["lines"][:20]}
                             for r in keyword_rank(analysis.records)[:3]],
        "similar_cards": [],
    }

    if not suspicious:
        report["root_cause"] = not_sure("nothing in the log was flagged as suspicious")
    elif not use_llm or llm is None or kb is None:
        report["root_cause"] = not_sure("LLM step skipped")
    else:
        query = "\n".join(f"{g.template}\n{g.example}" for g in suspicious[:MAX_GROUPS])
        cards = kb.search(query, k=3)
        report["similar_cards"] = [{"id": c.id, "title": c.title, "similarity": s, "fix_steps": c.fix_steps}
                                   for c, s in cards]
        prompt = build_prompt(suspicious, [c for c, _ in cards], by_line)
        schema = answer_schema(sorted(kb.cards))
        t_llm = time.perf_counter()
        try:
            raw = llm.complete(SYSTEM_PROMPT, prompt, schema)
            answer = parse_answer(raw)
            rc = verify_answer(answer, by_line, set(kb.cards))
            report["root_cause"] = apply_kb(rc, kb, {c.id: s for c, s in cards})
        except Exception as exc:  # LLM down, bad JSON, timeout: say so instead of guessing
            report["root_cause"] = not_sure(f"LLM step failed: {type(exc).__name__}: {exc}"[:300])
        report["stats"]["llm_seconds"] = round(time.perf_counter() - t_llm, 2)

    report["stats"]["seconds"] = round(time.perf_counter() - t0, 2)
    return report


_kb: KnowledgeBase | None = None


def default_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb


def default_llm() -> LLMClient:
    return OllamaClient()
