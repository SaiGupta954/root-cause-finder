"""HTTP API.

    POST /analyze          upload a log file (multipart "file") or paste lines (form field "text")
    GET  /analyses/{id}    a saved result
    GET  /analyses         recent results
    GET  /health           API, LLM and model status
    GET  /samples          sample logs for the one-click demo; GET /samples/{name} returns one

Run: uvicorn app:app --app-dir backend --reload
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from rcf.llm import MODEL, OLLAMA_HOST
from rcf.pipeline import default_kb, default_llm, find_root_cause

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get("RCF_DB", ROOT / "data" / "rcf.db"))
SAMPLES_DIR = Path(os.environ.get("RCF_SAMPLES_DIR", ROOT / "data" / "samples"))
MAX_BYTES = int(os.environ.get("RCF_MAX_MB", "20")) * 1024 * 1024

app = FastAPI(title="Root Cause Finder", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("RCF_CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


def db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS analyses (
               id TEXT PRIMARY KEY,
               created_at TEXT NOT NULL,
               filename TEXT,
               status TEXT NOT NULL,
               root_cause TEXT,
               report TEXT NOT NULL
           )"""
    )
    return conn


def decode_log(data: bytes) -> list[str]:
    """Bytes -> lines, or a 400 with a message a person can act on."""
    if not data.strip():
        raise HTTPException(400, "The file is empty. Upload a log file with at least one line.")
    if b"\x00" in data[:8192]:
        raise HTTPException(400, "This looks like a binary file (for example a .gz, image or journal file), "
                                 "not a text log. Export it as text first, e.g. `journalctl > log.txt`.")
    text = data.decode("utf-8", errors="replace")
    if text.count("�") > len(text) * 0.05:
        raise HTTPException(400, "The file is not readable as UTF-8 text.")
    lines = text.splitlines()
    if not any(line.strip() for line in lines):
        raise HTTPException(400, "The file has no readable lines.")
    return lines


def read_limited(upload: UploadFile) -> bytes:
    data = upload.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, f"The file is larger than {MAX_BYTES // (1024 * 1024)} MB. "
                                 "Upload only the part of the log around the failure.")
    return data


@app.post("/analyze")
def analyze(
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
    use_llm: bool = Query(True, description="false = parsing and flagging only, no LLM"),
):
    # A sync endpoint: FastAPI runs it in a worker thread, so a slow LLM call does not block other requests.
    if file is not None and file.filename:
        data, filename = read_limited(file), file.filename
    elif text:
        data, filename = text.encode("utf-8"), "pasted.log"
        if len(data) > MAX_BYTES:
            raise HTTPException(413, f"The pasted text is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    else:
        raise HTTPException(400, "Send a log file (field 'file') or pasted lines (field 'text').")

    lines = decode_log(data)
    report = find_root_cause(lines, default_kb() if use_llm else None, default_llm() if use_llm else None,
                             use_llm=use_llm)

    analysis_id = uuid.uuid4().hex[:12]
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = {"id": analysis_id, "created_at": created, "filename": filename, **report}
    with db() as conn:
        conn.execute(
            "INSERT INTO analyses (id, created_at, filename, status, root_cause, report) VALUES (?,?,?,?,?,?)",
            (analysis_id, created, filename, report["root_cause"]["status"], report["root_cause"]["root_cause"],
             json.dumps(result)),
        )
    return result


@app.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str):
    with db() as conn:
        row = conn.execute("SELECT report FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"No analysis with id '{analysis_id}'.")
    return json.loads(row["report"])


@app.get("/analyses")
def list_analyses(limit: int = Query(20, ge=1, le=100)):
    with db() as conn:
        rows = conn.execute(
            "SELECT id, created_at, filename, status, root_cause FROM analyses ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/health")
def health():
    llm = {"host": OLLAMA_HOST, "model": MODEL, "reachable": False, "model_pulled": False}
    try:
        tags = httpx.get(f"{OLLAMA_HOST}/api/tags", timeout=3).json()
        llm["reachable"] = True
        llm["model_pulled"] = any(m["name"] in (MODEL, f"{MODEL}:latest") for m in tags.get("models", []))
    except (httpx.HTTPError, ValueError):
        pass
    return {"status": "ok", "llm": llm, "max_upload_mb": MAX_BYTES // (1024 * 1024)}


@app.get("/samples")
def list_samples():
    if not SAMPLES_DIR.is_dir():
        return []
    labels = {}
    if (SAMPLES_DIR / "samples.json").is_file():
        labels = json.loads((SAMPLES_DIR / "samples.json").read_text())
    return [{"name": p.name, "title": labels.get(p.name, p.stem), "bytes": p.stat().st_size}
            for p in sorted(SAMPLES_DIR.glob("*.log"))]


@app.get("/samples/{name}", response_class=PlainTextResponse)
def get_sample(name: str):
    if not re.fullmatch(r"[\w.-]+\.log", name) or not (SAMPLES_DIR / name).is_file():
        raise HTTPException(404, f"No sample named '{name}'.")
    return (SAMPLES_DIR / name).read_text(encoding="utf-8", errors="replace")
