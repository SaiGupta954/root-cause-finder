---
id: port_in_use
title: Port already in use
---
## Symptoms
A server fails to start: "Address already in use" (EADDRINUSE, errno 98), "bind() to 0.0.0.0:80 failed", "could not bind", "failed to listen on port", "port is already allocated".

## Cause
Another process (often an old instance of the same service, or a different server) is already listening on the same IP and port.

## Fix
- Find who holds the port: `ss -ltnp 'sport = :<port>'` or `lsof -i :<port>`.
- Stop the old or duplicate process, or move one service to another port.
- Look for duplicate service units, containers or a second instance started by mistake.
