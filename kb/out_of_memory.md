---
id: out_of_memory
title: Out of memory (OOM)
---
## Symptoms
"Out of memory", "Cannot allocate memory" (ENOMEM), "MemoryError", "Killed", "oom-killer", "Out of memory: Killed process", "invoked oom-killer", exit code 137, "JavaScript heap out of memory", "fatal error: runtime: out of memory". The process dies suddenly with no clean shutdown.

## Cause
A process (or container) used more memory than is available or allowed by its cgroup/container limit, often due to a memory leak, an oversized cache or batch, or a limit set too low.

## Fix
- Confirm the OOM kill: `dmesg -T | grep -i -E 'killed process|out of memory'` or `journalctl -k`.
- Check the memory limit and usage (`docker stats`, cgroup `memory.max`, `ulimit -v`, heap flags).
- Find the leak or oversized batch/cache in the process that grew.
- Raise the limit or add swap only after fixing the growth.
