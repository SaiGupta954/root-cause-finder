---
id: crash_loop
title: Service stuck in a crash/restart loop
---
## Symptoms
The same service starts, exits and is restarted again and again: "Main process exited, code=exited, status=1/FAILURE", "Scheduled restart job, restart counter is at N", "start request repeated too quickly", "Start request repeated too quickly", "Failed with result 'exit-code'". The same startup lines repeat.

## Cause
The service exits right after starting, often because of a missing dependency, a bad environment variable, a missing file, or an application bug. The supervisor (systemd, supervisord, a container restart policy) keeps restarting it.

## Fix
- Read the lines just before each exit to see why the process stops.
- Check `systemctl status <service>` and `journalctl -u <service> -n 100` (or `docker logs` / the supervisor log).
- Run the start command by hand with the same user and environment.
- Fix the error (missing env var, file, module or dependency), then `systemctl reset-failed` and restart.
