import json

import pytest
from fastapi.testclient import TestClient

import app as api
from rcf import pipeline
from test_verify import FakeKB, FakeLLM, answer


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(api, "SAMPLES_DIR", tmp_path / "samples")
    reply = answer([{"line": 27, "text": "could not extend file /var/lib/postgresql/data/base/16384/2619"}])
    monkeypatch.setattr(api, "default_kb", lambda: FakeKB())
    monkeypatch.setattr(api, "default_llm", lambda: FakeLLM(reply))
    return TestClient(api.app)


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["max_upload_mb"] == 20


def test_analyze_upload_then_fetch(client, data_path):
    with open(data_path("disk_full_40.log"), "rb") as fh:
        r = client.post("/analyze", files={"file": ("disk.log", fh, "text/plain")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["filename"] == "disk.log"
    assert body["root_cause"]["category"] == "disk_full"
    assert body["root_cause"]["evidence_lines"][0]["line"] == 27
    assert body["top_groups"][0]["flags"] == ["error_words", "new_pattern", "spike"]

    saved = client.get(f"/analyses/{body['id']}").json()
    assert saved == body
    assert client.get("/analyses").json()[0]["id"] == body["id"]


def test_analyze_pasted_text_without_llm(client, data_path):
    text = open(data_path("disk_full_40.log")).read()
    body = client.post("/analyze?use_llm=false", data={"text": text}).json()
    assert body["filename"] == "pasted.log"
    assert body["root_cause"]["status"] == "not_sure"
    assert body["stats"]["flagged"] == 3


@pytest.mark.parametrize("content, message", [
    (b"", "empty"),
    (b"\n\n  \n", "empty"),
    (b"\x1f\x8b\x08\x00\x00binary", "binary"),
])
def test_bad_files_get_clear_errors(client, content, message):
    r = client.post("/analyze", files={"file": ("x.log", content, "text/plain")})
    assert r.status_code == 400
    assert message in r.json()["detail"]


def test_file_too_large(client, monkeypatch):
    monkeypatch.setattr(api, "MAX_BYTES", 100)
    r = client.post("/analyze", files={"file": ("big.log", b"x" * 101, "text/plain")})
    assert r.status_code == 413
    assert "larger than" in r.json()["detail"]


def test_nothing_sent(client):
    r = client.post("/analyze")
    assert r.status_code == 400


def test_unknown_analysis_is_404(client):
    assert client.get("/analyses/nope").status_code == 404


def test_samples(client, tmp_path):
    (tmp_path / "samples").mkdir()
    (tmp_path / "samples" / "disk_full.log").write_text("Oct 11 09:00:00 h app[1]: hi\n")
    (tmp_path / "samples" / "samples.json").write_text(json.dumps({"disk_full.log": "Disk full"}))
    assert client.get("/samples").json() == [{"name": "disk_full.log", "title": "Disk full", "bytes": 29}]
    assert client.get("/samples/disk_full.log").text.startswith("Oct 11")
    assert client.get("/samples/..%2Fetc%2Fpasswd").status_code == 404
