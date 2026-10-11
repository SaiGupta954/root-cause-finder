import json

import pytest

from rcf.pipeline import find_root_cause
from rcf.verify import NOT_SURE, verify_answer

LINES = {
    1: "Oct 11 09:20:02 web01 kernel: EXT4-fs warning (device sda1): Directory index full!",
    2: "Oct 11 09:20:03 web01 postgres[4410]: ERROR: could not extend file /var/lib/x: No space left on device",
    3: "Oct 11 09:20:14 web01 nginx[880]: open() /var/log/nginx/access.log failed (28: No space left on device)",
}
CATS = {"disk_full", "out_of_memory"}


def answer(evidence, **kw):
    base = {"root_cause": "Disk on web01 is full", "category": "disk_full", "alternatives": ["out_of_memory"],
            "confidence": 0.8, "evidence_lines": evidence, "next_steps": ["df -h"]}
    return base | kw


def test_real_evidence_is_kept_and_replaced_with_the_real_line():
    out = verify_answer(answer([{"line": 2, "text": "could not extend file /var/lib/x: No space left"}]), LINES, CATS)
    assert out["status"] == "verified"
    assert out["evidence_lines"] == [{"line": 2, "text": LINES[2]}]
    assert out["confidence"] == 0.8


def test_made_up_line_number_is_dropped():
    out = verify_answer(answer([
        {"line": 2, "text": "No space left on device"},
        {"line": 999, "text": "No space left on device"},
    ]), LINES, CATS)
    assert [e["line"] for e in out["evidence_lines"]] == [2]
    assert out["dropped_evidence"][0]["reason"] == "line 999 does not exist in the file"
    assert out["confidence"] == 0.4  # half the evidence failed, so half the confidence


def test_quote_that_does_not_match_its_line_is_dropped():
    # Real line number, but the text belongs to another line.
    out = verify_answer(answer([{"line": 1, "text": "No space left on device"}]), LINES, CATS)
    assert out["root_cause"] == NOT_SURE
    assert "does not match line 1" in out["dropped_evidence"][0]["reason"]


def test_invented_text_on_real_line_gives_not_sure():
    out = verify_answer(answer([{"line": 3, "text": "Out of memory: Killed process 4410 (postgres)"}]), LINES, CATS)
    assert out["status"] == "not_sure"
    assert out["root_cause"] == NOT_SURE
    assert out["confidence"] == 0.0 and out["evidence_lines"] == []
    assert out["unverified_guess"] == "Disk on web01 is full"


@pytest.mark.parametrize("bad", [
    {"line": "abc", "text": "No space left on device"},
    {"line": 2, "text": "ERROR"},  # too short to prove anything
    "line 2",
    {"text": "No space left on device"},
])
def test_malformed_evidence_is_dropped(bad):
    out = verify_answer(answer([bad]), LINES, CATS)
    assert out["status"] == "not_sure"


def test_no_evidence_at_all_gives_not_sure():
    assert verify_answer(answer([]), LINES, CATS)["root_cause"] == NOT_SURE


def test_whitespace_differences_are_ok_and_duplicates_collapse():
    ev = [{"line": 3, "text": "open()  /var/log/nginx/access.log   failed"}, {"line": 3, "text": "No space left on device"}]
    out = verify_answer(answer(ev), LINES, CATS)
    assert [e["line"] for e in out["evidence_lines"]] == [3]


def test_unknown_category_and_alternatives_are_cleaned():
    out = verify_answer(answer([{"line": 2, "text": "No space left on device"}], category="aliens",
                               alternatives=["disk_full", "aliens", "out_of_memory"], confidence=7), LINES, CATS)
    assert out["category"] == "other"
    assert out["alternatives"] == ["disk_full", "out_of_memory"]
    assert out["confidence"] == 1.0


# ---- the whole pipeline with a fake LLM (no Ollama needed) ----

class FakeLLM:
    def __init__(self, reply):
        self.reply, self.prompt = reply, None

    def complete(self, system, user, schema):
        self.prompt = user
        return self.reply if isinstance(self.reply, str) else json.dumps(self.reply)


class FakeKB:
    def __init__(self):
        from rcf.kb import load_cards
        self.cards = {c.id: c for c in load_cards()}

    def search(self, query, k=3):
        return [(self.cards["disk_full"], 0.9)]


def _lines(data_path):
    return open(data_path("disk_full_40.log")).readlines()


def test_pipeline_with_fake_llm_keeps_real_evidence(data_path):
    llm = FakeLLM(answer([{"line": 27, "text": "could not extend file /var/lib/postgresql/data/base/16384/2619"},
                          {"line": 4242, "text": "made up line"}]))
    report = find_root_cause(_lines(data_path), FakeKB(), llm)
    rc = report["root_cause"]
    assert rc["status"] == "verified" and rc["category"] == "disk_full"
    assert [e["line"] for e in rc["evidence_lines"]] == [27]
    assert len(rc["dropped_evidence"]) == 1
    # The LLM only saw flagged groups with their real line numbers, and the KB card.
    assert "L27: Oct 11 09:20:03" in llm.prompt and "Card disk_full" in llm.prompt
    assert "CRON" not in llm.prompt
    assert report["stats"]["flagged"] == 3 and report["timeline"]


def test_pipeline_with_only_fake_evidence_says_not_sure(data_path):
    llm = FakeLLM(answer([{"line": 4242, "text": "No space left on device at all"}]))
    rc = find_root_cause(_lines(data_path), FakeKB(), llm)["root_cause"]
    assert rc["root_cause"] == NOT_SURE


def test_pipeline_survives_broken_llm_output(data_path):
    rc = find_root_cause(_lines(data_path), FakeKB(), FakeLLM("not json {"))["root_cause"]
    assert rc["root_cause"] == NOT_SURE and "LLM step failed" in rc["error"]


def test_pipeline_skips_llm_for_a_clean_log(data_path):
    llm = FakeLLM("should not be called")
    report = find_root_cause(open(data_path("normal_20.log")).readlines(), FakeKB(), llm)
    assert llm.prompt is None
    assert report["root_cause"]["root_cause"] == NOT_SURE


# ---- alternatives and next steps are decided by plain code, not the LLM ----

class ScoredKB(FakeKB):
    """KB search with fixed similarities, like the real SSH brute-force run (0.75 vs 0.27)."""

    def __init__(self, scores):
        super().__init__()
        self.scores = scores

    def search(self, query, k=3):
        return [(self.cards[c], s) for c, s in self.scores][:k]


def _ssh_lines(data_path):
    return open(data_path("ssh_bruteforce_30.log")).readlines()


def test_far_alternative_is_dropped_and_steps_come_from_the_card(data_path):
    reply = answer([{"line": 6, "text": "Failed password for root from 173.234.31.186 port 38926 ssh2"}],
                   category="ssh_bruteforce", alternatives=["port_in_use"])
    reply["next_steps"] = ["Run `sshd -t` to check for syntax errors in the config file"]  # ignored
    kb = ScoredKB([("ssh_bruteforce", 0.747), ("port_in_use", 0.27), ("bad_config", 0.21)])
    rc = find_root_cause(_ssh_lines(data_path), kb, FakeLLM(reply))["root_cause"]
    assert rc["category"] == "ssh_bruteforce"
    assert rc["alternatives"] == []
    assert rc["next_steps"] == kb.cards["ssh_bruteforce"].fix_steps
    assert not any("sshd -t" in s for s in rc["next_steps"])
    assert rc["next_steps_source"] == "ssh_bruteforce"


def test_close_alternative_is_kept(data_path):
    reply = answer([{"line": 27, "text": "No space left on device"}], alternatives=["permission_denied", "out_of_memory"])
    kb = ScoredKB([("disk_full", 0.50), ("permission_denied", 0.45), ("out_of_memory", 0.20)])
    rc = find_root_cause(_lines(data_path), kb, FakeLLM(reply))["root_cause"]
    assert rc["alternatives"] == ["permission_denied"]  # 0.45 >= 0.8 * 0.50; 0.20 is too far


def test_other_category_gets_no_next_steps(data_path):
    reply = answer([{"line": 27, "text": "No space left on device"}], category="other", alternatives=[])
    rc = find_root_cause(_lines(data_path), FakeKB(), FakeLLM(reply))["root_cause"]
    assert rc["category"] == "other" and rc["next_steps"] == []


def test_report_carries_the_similar_cards(data_path):
    report = find_root_cause(_lines(data_path), FakeKB(), FakeLLM(answer([{"line": 27, "text": "No space left on device"}])))
    assert report["similar_cards"][0]["id"] == "disk_full"
    assert report["similar_cards"][0]["fix_steps"]


def test_llm_schema_has_no_next_steps():
    from rcf.llm import SYSTEM_PROMPT, answer_schema
    assert "next_steps" not in answer_schema(["disk_full"])["properties"]
    assert "next_steps" not in SYSTEM_PROMPT
