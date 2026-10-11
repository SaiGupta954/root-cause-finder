"""Knowledge base of known failures: one Markdown card per failure type, searched with Chroma."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KB_DIR = Path(os.environ.get("RCF_KB_DIR", ROOT / "kb"))
CHROMA_DIR = Path(os.environ.get("RCF_CHROMA_DIR", ROOT / "data" / "chroma"))
COLLECTION = "failure_cards"


@dataclass
class Card:
    id: str
    title: str
    symptoms: str
    cause: str
    fix: str

    def text(self) -> str:
        return f"{self.title}\nSymptoms: {self.symptoms}\nCause: {self.cause}\nFix: {self.fix}"


def parse_card(path: Path) -> Card:
    raw = path.read_text(encoding="utf-8")
    meta = dict(re.findall(r"^(\w+):\s*(.+)$", raw.split("---")[1], re.MULTILINE))
    sections = dict(
        (name.lower(), body.strip())
        for name, body in re.findall(r"^## (\w+)\n(.*?)(?=^## |\Z)", raw, re.MULTILINE | re.DOTALL)
    )
    return Card(meta["id"], meta["title"], sections["symptoms"], sections["cause"], sections["fix"])


def load_cards(kb_dir: Path = KB_DIR) -> list[Card]:
    return [parse_card(p) for p in sorted(kb_dir.glob("*.md"))]


class KnowledgeBase:
    def __init__(self, kb_dir: Path = KB_DIR, chroma_dir: Path | None = CHROMA_DIR):
        import chromadb  # imported here so the parser and tests don't pay for it

        self.cards = {c.id: c for c in load_cards(kb_dir)}
        client = chromadb.PersistentClient(path=str(chroma_dir)) if chroma_dir else chromadb.EphemeralClient()
        self.collection = client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
        # Upsert every start: the cards are tiny and this keeps Chroma in sync with kb/.
        self.collection.upsert(
            ids=list(self.cards),
            documents=[c.text() for c in self.cards.values()],
            metadatas=[{"title": c.title} for c in self.cards.values()],
        )
        stale = set(self.collection.get()["ids"]) - set(self.cards)
        if stale:
            self.collection.delete(ids=list(stale))

    def search(self, query: str, k: int = 3) -> list[tuple[Card, float]]:
        res = self.collection.query(query_texts=[query], n_results=min(k, len(self.cards)))
        return [(self.cards[i], round(1 - d, 3)) for i, d in zip(res["ids"][0], res["distances"][0])]
