---
id: out_of_memory
title: Out of memory (OOM)
---
## Symptoms
"Out of memory", "Cannot allocate memory" (ENOMEM), "MemoryError", "Killed", "oom-killer", "Out of memory: Killed process", "invoked oom-killer", exit code 137, "JavaScript heap out of memory", "fatal error: runtime: out of memory". The process dies suddenly with no clean shutdown.

## Cause
A process (or container) used more memory than is available or allowed by its cgroup/container limit, often due to a memory leak, an oversized cache or batch, or a limit set too low.

## Fix
Find the process in `dmesg` / `journalctl -k` OOM lines. Check limits (`docker stats`, cgroup memory.max). Fix the leak, lower batch sizes, add swap, or raise the memory limit.
