---
id: disk_full
title: Disk or filesystem full
---
## Symptoms
"No space left on device" (errno 28, ENOSPC) from many programs at once. Writes fail: could not write, could not extend file, write error, failed to write to log, journal or temp file. Databases refuse new data. Log rotation or package installs fail.

## Cause
A filesystem reached 100% of its blocks (or ran out of inodes). Usually a growing log, a large temp or cache file, core dumps, or a runaway process writing to disk.

## Fix
Check usage with `df -h` and inodes with `df -i`. Find large files with `du -xh / | sort -h | tail`. Delete or rotate old logs, clean caches, restart the service that holds deleted files open (`lsof +L1`). Add monitoring and log rotation.
