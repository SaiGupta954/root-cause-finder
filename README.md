# Root Cause Finder

Upload a Linux log file and get back the most likely root cause, with the exact log lines as proof.

> Work in progress. Week 1 of 4 (parsing, grouping and flagging) is done.

## How it works

1. Upload a log file, or paste log lines.
2. **Parse** each line into a pattern plus its values with [Drain3](https://github.com/logpai/Drain3), so many lines become one pattern: `sshd: Failed password for root from <IP> port <NUM> ssh2`.
3. **Group** by pattern: count, first seen, last seen, count per minute.
4. **Flag** unusual groups with simple rules: error words, new patterns, and spikes over 3x the normal rate.
5. *(Week 2)* Look up past fixes in a small knowledge base with vector search (Chroma).
6. *(Week 2)* An LLM explains the flagged groups and the matching past fixes.
7. *(Week 2)* Plain code checks that every evidence line really exists. If none holds up, the answer is "not sure".
8. *(Week 3)* Web page with an error timeline, top error groups and a root cause card.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python analyze.py tests/data/disk_full_40.log
python analyze.py tests/data/disk_full_40.log --baseline tests/data/normal_20.log   # "new" = not in the normal log
./scripts/download_loghub.sh && python analyze.py data/Linux_2k.log
python -m pytest -q
```

Without `--baseline`, a pattern counts as "new" when it first appears in the second half of the log.

## Data

Public logs from [Loghub](https://github.com/logpai/loghub). See [data/README.md](data/README.md) for the citation.
