"""Run every failure-lab case through the full pipeline and through the keyword-only baseline.

    python scripts/evaluate.py | tee results/eval_output.txt
    python scripts/evaluate.py --cases disk_full_redis bad_config_redis
    python scripts/evaluate.py --no-llm        # baseline only

Scoring: a case is top-1 correct when the first answer's category equals the label, and top-3 correct
when the label is among the first three categories. "not sure" counts as wrong. Per-case results are
also written to results/eval_results.json.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from rcf import analyze_lines  # noqa: E402
from rcf.baseline import keyword_rank  # noqa: E402
from rcf.llm import MODEL  # noqa: E402
from rcf.pipeline import default_kb, default_llm, find_root_cause  # noqa: E402

LAB = ROOT / "data" / "failure_lab"


def run_case(case: dict, use_llm: bool) -> dict:
    lines = (LAB / f"{case['case']}.log").read_text(encoding="utf-8", errors="replace").splitlines()
    truth = case["category"]

    t0 = time.perf_counter()
    kw = keyword_rank(analyze_lines(lines).records)
    kw_seconds = time.perf_counter() - t0
    kw_cats = [r["category"] for r in kw[:3]]

    out = {
        "case": case["case"], "truth": truth, "lines": len(lines),
        "keyword": {"top3": kw_cats, "top1_ok": kw_cats[:1] == [truth], "top3_ok": truth in kw_cats,
                    "seconds": round(kw_seconds, 2)},
    }
    if use_llm:
        report = find_root_cause(lines, default_kb(), default_llm())
        rc = report["root_cause"]
        cats = [] if rc["status"] == "not_sure" else [rc["category"], *rc["alternatives"]][:3]
        out["llm"] = {
            "top3": cats, "top1_ok": cats[:1] == [truth], "top3_ok": truth in cats,
            "status": rc["status"], "root_cause": rc["root_cause"], "confidence": rc["confidence"],
            "evidence": [e["line"] for e in rc["evidence_lines"]], "dropped": len(rc.get("dropped_evidence", [])),
            "error": rc.get("error"), "kb_top": [c["id"] for c in report["similar_cards"]],
            "seconds": report["stats"]["seconds"],
        }
    return out


def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else "0/0"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", nargs="*", help="only these case ids")
    ap.add_argument("--no-llm", action="store_true", help="keyword baseline only")
    args = ap.parse_args()

    labels = json.loads((LAB / "labels.json").read_text())
    if args.cases:
        labels = [c for c in labels if c["case"] in args.cases]
    missing = [c["case"] for c in labels if not (LAB / f"{c['case']}.log").exists()]
    labels = [c for c in labels if c["case"] not in missing]

    git = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    print(f"Root Cause Finder evaluation  {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}  commit {git}")
    print(f"model: {MODEL if not args.no_llm else '(none)'}  machine: {platform.machine()} {platform.system()}  "
          f"cases: {len(labels)}" + (f"  missing logs: {', '.join(missing)}" if missing else ""))
    print()

    results = []
    header = f"{'case':38} {'truth':18} {'keyword top-3':42}" + ("" if args.no_llm else f" {'LLM top-3':42} {'sec':>6}")
    print(header)
    print("-" * len(header))
    for case in labels:
        r = run_case(case, use_llm=not args.no_llm)
        results.append(r)
        kw = ("✓ " if r["keyword"]["top1_ok"] else "~ " if r["keyword"]["top3_ok"] else "✗ ") + ",".join(r["keyword"]["top3"] or ["-"])
        row = f"{r['case']:38} {r['truth']:18} {kw:42}"
        if "llm" in r:
            m = r["llm"]
            llm = ("✓ " if m["top1_ok"] else "~ " if m["top3_ok"] else "✗ ") + (",".join(m["top3"]) or "not sure")
            row += f" {llm:42} {m['seconds']:6.1f}"
        print(row, flush=True)

    n = len(results)
    print()
    print("✓ = right as first answer, ~ = right in top 3, ✗ = wrong")
    print()
    print("SUMMARY")
    print(f"  keyword rules only   top-1 {pct(sum(r['keyword']['top1_ok'] for r in results), n):12}  "
          f"top-3 {pct(sum(r['keyword']['top3_ok'] for r in results), n):12}  "
          f"avg {statistics.mean(r['keyword']['seconds'] for r in results) if n else 0:.2f}s/log")
    if not args.no_llm and n:
        llm = [r["llm"] for r in results]
        print(f"  full pipeline (LLM)  top-1 {pct(sum(m['top1_ok'] for m in llm), n):12}  "
              f"top-3 {pct(sum(m['top3_ok'] for m in llm), n):12}  "
              f"avg {statistics.mean(m['seconds'] for m in llm):.1f}s/log  "
              f"(median {statistics.median(m['seconds'] for m in llm):.1f}s, max {max(m['seconds'] for m in llm):.1f}s)")
        print(f"  'not sure' answers: {sum(m['status'] == 'not_sure' for m in llm)}   "
              f"evidence lines dropped by the check: {sum(m['dropped'] for m in llm)}")
        wrong = [r for r in results if not r["llm"]["top1_ok"]]
        if wrong:
            print()
            print("LLM MISSES (top-1)")
            for r in wrong:
                m = r["llm"]
                print(f"  {r['case']}: truth={r['truth']} answer={m['top3'] or 'not sure'} kb_top={m['kb_top']}")
                print(f"      said: {m['root_cause'][:200]}" + (f"  [{m['error'][:120]}]" if m["error"] else ""))

    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "eval_results.json").write_text(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
