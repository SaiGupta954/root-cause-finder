# Root Cause Finder

![tests](BADGE_URL)

Upload a Linux log file and get back the most likely root cause, **with the exact log lines as proof**.
An LLM suggests the cause, and plain code checks that every log line it points to really exists.

<!-- DEMO: add a GIF or video here -->

## How it works

1. **Upload** a log file (syslog, auth.log, journalctl, `docker logs -t` output) or paste lines.
2. **Parse** each line into a pattern plus its values with [Drain3](https://github.com/logpai/Drain3). Many lines become
   one pattern, e.g. `sshd: Failed password for root from <IP> port <NUM> ssh2`.
3. **Group** by pattern: count, first seen, last seen, count per minute.
4. **Flag** unusual groups with simple rules: error words, brand-new patterns, and spikes over 3x the normal rate.
5. **Look up past fixes**: the flagged groups are matched against a small knowledge base of known failures
   (`kb/`, one card per failure type) with vector search in [Chroma](https://www.trychroma.com/).
6. **Explain with an LLM** (llama3.1:8b through [Ollama](https://ollama.com), so logs stay on your machine).
   It sees only the flagged groups, with their real line numbers, and the 3 closest cards. It must answer in JSON:
   root cause, category, confidence and evidence lines.
7. **Check the answer with plain code.** Every evidence line number must exist and the quoted text must be on that
   line; anything else is dropped. With no evidence left, the answer is **"not sure"** instead of a guess.
   Next steps come from the chosen category's knowledge card, never from the LLM, and a second category is
   shown only if its card matched nearly as well as the first.
8. **Show it** on a web page: errors-per-minute timeline, top suspicious groups, and a root cause card with the
   evidence lines highlighted and a "Copy report" button.

## Results

Tested on the 30 failures from the [failure lab](#the-failure-lab) (below), each with a known true root cause.
"Keyword rules only" is a baseline with no LLM and no vector search: hand-written regexes per failure type,
and the type with the most matching lines wins. The regexes were written before any failure-lab log existed and
were not changed after seeing results.

| | Right root cause, first answer | Right root cause, in top 3 | Time per log |
|---|---|---|---|
| **Full pipeline** (rules + Chroma + llama3.1:8b + check) | **23 / 30 (77%)** | 23 / 30 (77%) | 33.8 s average, 37.3 s median, 52.4 s max |
| Keyword rules only | 19 / 30 (63%) | 19 / 30 (63%) | 0.01 s |

Measured on an Apple M3 (16 GB) with Ollama on the GPU, commit `a746204`, 2026-10-11. The average time includes
4 logs answered "not sure" in about 0 s, because nothing was flagged and the LLM was never called.
Raw output: [results/eval_output.txt](results/eval_output.txt) (from
`python -u scripts/evaluate.py 2>&1 | grep -v -i warning | tee results/eval_output.txt`; the grep removes library
warnings printed to stderr); per-case details:
[results/eval_results.json](results/eval_results.json).

| Failure type | Cases | Keyword rules | Full pipeline |
|---|---|---|---|
| Disk full | 4 | 3 | 4 |
| Wrong DNS server | 4 | 2 | 3 |
| Crash loop | 4 | 0 | 3 |
| Permission denied | 4 | 4 | 4 |
| Port in use | 4 | 2 | 3 |
| Out of memory | 4 | 3 | 2 |
| Bad config | 3 | 2 | 1 |
| SSH brute force | 3 | 3 | 3 |

**What the AI adds:** the pipeline got 8 cases right that the keyword rules missed, mostly where the log never uses
the obvious words: Redis's "Short write while writing to the AOF file" (disk full), nginx "could not be resolved"
(DNS), supervisord "exited: app … not expected" (crash loops), Redis "FATAL CONFIG FILE ERROR". The keyword rules
got 4 right that the pipeline missed.

**The check step:** across all 30 runs the LLM quoted real lines every time, so no evidence line was dropped.
The check matters for the other direction: whenever nothing could be verified, the app said "not sure" instead of
inventing an answer (4 times, all because nothing was flagged).

**Where top-3 doesn't help:** a second category is shown only if its knowledge card matched nearly as well as the
first one. In this run that never rescued a wrong first answer, so top-3 equals top-1.

### The 7 misses and why

| Case | Answer | Why |
|---|---|---|
| `port_in_use_python_api` | not sure | The only error is a Python traceback ending in `OSError: [Errno 98] Address in use`. The flag rules match whole words, so `OSError` doesn't count as "error", and "Address in use" isn't on the list. Nothing was flagged. |
| `out_of_memory_cgroup_kill` | not sure | The kernel kills the process; the only trace is bash's `Killed python …` line. "Killed" alone isn't an error word ("killed process" is), so nothing was flagged. |
| `out_of_memory_python_memoryerror` | not sure | The traceback ends with a one-word line, `MemoryError`. Drain merged it with the `^^^^^` marker line into the pattern `<*>`, so the word disappeared from the pattern, and `error` wouldn't match inside it anyway. Nothing was flagged. |
| `bad_config_nginx_typo` | not sure | `[emerg] unknown directive "listn"` is parsed as CRITICAL, but **the flag rules ignore the log level**. The line has no error word, so nothing was flagged. |
| `bad_config_postgres` | permission denied | The LLM's sentence was right ("invalid value for the shared_buffers parameter"), but vector search didn't put the bad-config card in the top 3, and the model picked a category from the cards it was shown. |
| `dns_failure_wget` | port in use | busybox wget says `bad address 'example.com'`, which matches nothing in the DNS card, so the DNS card wasn't retrieved and the model guessed wrong. |
| `crash_loop_docker_restart` | bad config | Node.js exits with `Cannot find module '/etc/api/config.json'` and Docker restarts it. "Missing config file" is arguably a config problem; the label says crash loop. The model also invented a detail ("missing semicolon"); the check verifies evidence lines, not the explanation. |

Four of the seven misses come from the flag rules, not the LLM. The obvious fixes: flag CRITICAL/ERROR lines even
without an error word, and match error words inside identifiers like `MemoryError`. They are **not** applied
here, because tuning on the test set would make these numbers look better than they are. A fair re-test needs new
failure cases.

## Run it

**With Docker** (one command; the first start downloads the model, about 4.9 GB):

```bash
docker compose up --build
```

Open http://localhost:8080 and click one of the three sample logs. On a Mac, Docker has no GPU access, so the LLM
runs on CPU: 142 s for one sample log in our test, and the Docker VM needs about 10 GB of memory. If Ollama is
installed on the Mac, use it instead (it uses the GPU):

```bash
ollama pull llama3.1:8b
OLLAMA_HOST=http://host.docker.internal:11434 docker compose up --build
```

**Without Docker** (Python 3.12, Node 20+, Ollama):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ollama pull llama3.1:8b
uvicorn app:app --app-dir backend --port 8000        # API
npm --prefix frontend install && npm --prefix frontend run dev   # web app on http://localhost:5173
```

**Command line:**

```bash
python analyze.py data/failure_lab/disk_full_postgres.log             # suspicious groups only
python analyze.py data/failure_lab/disk_full_postgres.log --explain   # plus the LLM root cause
```

**Tests and evaluation:**

```bash
python -m pytest -q
./scripts/failure_lab/run_all.sh                        # recreate the 30 failure logs (needs Docker)
python scripts/evaluate.py | tee results/eval_output.txt
```

### API

| Method | Path | |
|---|---|---|
| `POST` | `/analyze` | multipart `file` or form field `text`; `?use_llm=false` for parsing and flagging only |
| `GET` | `/analyses/{id}` | a saved result (SQLite) |
| `GET` | `/analyses` | recent results |
| `GET` | `/health` | API and LLM status |
| `GET` | `/samples`, `/samples/{name}` | demo logs |

Uploads are limited to 20 MB. Empty, binary and unreadable files get a clear error message.

## The failure lab

There are no public logs labelled with *why* a system failed (Loghub labels only say normal or abnormal), so this
project builds its own test set. `scripts/failure_lab/` has one script per failure type. Each case starts fresh
Docker containers, **causes the failure for real**, and saves the container's `docker logs -t` output to
`data/failure_lab/<case>.log`. No log line is written or edited by hand. `data/failure_lab/labels.json` holds
the true root cause of each case.

| Failure type | Cases |
|---|---|
| Disk full | Postgres data dir, Redis AOF, nginx access log, Python export job |
| Wrong DNS server | wget, Python HTTP client, Python DB client (`127.0.0.1` resolver), nginx `resolver` |
| Crash loop | missing env var, missing Python module, segfault (all under supervisord), missing config file (Docker restart policy) |
| Permission denied | nginx web root, app log file, Postgres data dir, upload dir |
| Port in use | nginx, Redis, Postgres in a shared network namespace, Python API |
| Out of memory | container memory limit (OOM kill), `ulimit -v` MemoryError, Redis `maxmemory`, Node.js heap limit |
| Bad config | nginx unknown directive, Redis config value, Postgres parameter value |
| SSH brute force | root password guessing, user enumeration, three attacking hosts |

Recreate all 30 with `./scripts/failure_lab/run_all.sh` (about 5 minutes). One more case
(`bad_config_nginx_semicolon`) exists in the scripts but was left out of the set before any evaluation, to keep
30 cases with at most 4 per type.

## What it can't do yet

- **One root cause per log.** Several unrelated failures in one file get one answer.
- **Unflagged failures are invisible to the LLM.** The flag rules ignore log levels and match error words only
  as whole words, so a lone `[emerg]` line, `MemoryError` or `Killed` can go unflagged (4 of the 7 misses). Drain can also
  merge one-word lines (like `MemoryError`) into a bare `<*>` pattern.
- **Retrieval decides the category.** If vector search doesn't return the right card (wget's "bad address"),
  the model usually picks a wrong category even when its explanation is right.
- **The explanation text isn't checked.** Evidence lines are verified, but a detail in the sentence can still be
  made up.
- **The 8 failure types in the knowledge base.** Anything else can only be answered as "other", with no next steps.
- **Speed.** 37 s median per log with a local 8B model on an Apple M3 GPU, and 142 s for one sample log on CPU in Docker.
- **The test set is small and self-made.** 30 cases from one person's lab are a sanity check, not a benchmark.
  Real production logs are longer and noisier.
- **Formats.** Classic syslog, ISO-timestamp syslog and `docker logs -t` lines are parsed; other formats are
  analysed without timestamps.

## Data and credits

- Failure-lab logs (`data/failure_lab/`, `data/samples/`): created for this project by running real failures in
  Docker containers.
- Unit-test fixtures (`tests/data/`): small hand-written logs; see [tests/data/README.md](tests/data/README.md).
  `ssh_bruteforce_30.log` imitates the format of Loghub's OpenSSH log but is not copied from it.
- Loghub logs (downloaded by `scripts/download_loghub.sh`, not in the repo) were used to tune the flag rules.
  Loghub is free for research and academic use; please cite it:

  > Jieming Zhu, Shilin He, Pinjia He, Jinyang Liu, Michael R. Lyu. *Loghub: A Large Collection of System Log
  > Datasets for AI-driven Log Analytics.* IEEE ISSRE, 2023. https://github.com/logpai/loghub
