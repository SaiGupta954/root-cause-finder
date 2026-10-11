"""Ask an LLM for the root cause. It only sees the flagged groups (with real line numbers) and the closest KB cards."""

from __future__ import annotations

import json
import os
from typing import Protocol

import httpx

from .grouping import PatternGroup
from .kb import Card

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL = os.environ.get("RCF_MODEL", "llama3.1:8b")

MAX_GROUPS = 8
SAMPLES_PER_GROUP = 3
MAX_LINE_CHARS = 300


class LLMClient(Protocol):
    def complete(self, system: str, user: str, schema: dict) -> str: ...


class OllamaClient:
    def __init__(self, host: str = OLLAMA_HOST, model: str = MODEL, timeout: float = 180.0):
        self.host, self.model, self.timeout = host.rstrip("/"), model, timeout

    def complete(self, system: str, user: str, schema: dict) -> str:
        resp = httpx.post(
            f"{self.host}/api/chat",
            json={
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "format": schema,  # Ollama constrains the output to this JSON schema
                "stream": False,
                "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 500},
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]


def answer_schema(categories: list[str]) -> dict:
    cats = categories + ["other"]
    return {
        "type": "object",
        "properties": {
            "root_cause": {"type": "string"},
            "category": {"type": "string", "enum": cats},
            "alternatives": {"type": "array", "items": {"type": "string", "enum": cats}, "maxItems": 2},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "evidence_lines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"line": {"type": "integer"}, "text": {"type": "string"}},
                    "required": ["line", "text"],
                },
                "maxItems": 3,
            },
        },
        "required": ["root_cause", "category", "alternatives", "confidence", "evidence_lines"],
    }


SYSTEM_PROMPT = """You are a Linux site reliability engineer finding the root cause of a failure from logs.
You get suspicious log pattern groups (each sample line starts with its real line number, like "L42:")
and reference cards for known failure types.

Rules:
- Pick the single most likely root cause. The root cause is what started the failure, not a side effect.
- root_cause: one or two plain-English sentences saying what went wrong and where (name the service,
  file, port, host or user from the logs). Do not just repeat a card title or id.
- "category" is the id of the matching card, or "other" if none fits. "alternatives" are the next most
  likely ids, best first (at most 2, never the same as category).
- evidence_lines: 1 to 3 lines from the samples. "line" is the number after "L". "text" is an exact,
  character-for-character excerpt of that line (the message part, at most 120 characters).
  Never invent line numbers or text.
- confidence is between 0 and 1. Use a low value if the evidence is weak.
Answer with JSON only."""


def sample_lines(group: PatternGroup, by_line: dict[int, str]) -> list[int]:
    nums = group.line_numbers
    picks = nums[: SAMPLES_PER_GROUP - 1] + nums[-1:] if len(nums) > SAMPLES_PER_GROUP else nums
    return [n for n in picks if n in by_line]


def build_prompt(groups: list[PatternGroup], cards: list[Card], by_line: dict[int, str]) -> str:
    parts = ["## Suspicious log groups (most suspicious first)"]
    for i, g in enumerate(groups[:MAX_GROUPS], start=1):
        when = f"{g.first_seen:%Y-%m-%d %H:%M:%S}" if g.first_seen else "unknown"
        parts.append(
            f"\n### Group {i}: {g.template}\n"
            f"count={g.count}, first_seen={when}, flags={', '.join(g.flags)}\n"
            + "\n".join(f"- {r}" for r in g.reasons)
        )
        for n in sample_lines(g, by_line):
            parts.append(f"L{n}: {by_line[n][:MAX_LINE_CHARS]}")
    parts.append("\n## Reference cards for known failures")
    for c in cards:
        parts.append(f"\n### Card {c.id} ({c.title})\nSymptoms: {c.symptoms}\nCause: {c.cause}\nFix: {c.fix}")
    return "\n".join(parts)


def parse_answer(text: str) -> dict:
    """Parse the model output; tolerate a code fence around the JSON."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("LLM answer is not a JSON object")
    return data
