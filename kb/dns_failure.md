---
id: dns_failure
title: Wrong or unreachable DNS server
---
## Symptoms
Hostnames do not resolve: "Temporary failure in name resolution", "Name or service not known", "Could not resolve host", "getaddrinfo failed", "no servers could be reached", "connection timed out; no servers could be reached", EAI_AGAIN. Connections by IP address still work.

## Cause
/etc/resolv.conf points at a wrong, dead or unreachable nameserver, or the DNS server is down or blocked by a firewall.

## Fix
- Check which resolver is used: `cat /etc/resolv.conf` (or `resolvectl status`).
- Test it directly: `dig @<nameserver> example.com` and `getent hosts example.com`.
- Point to a working DNS server (fix the DHCP, systemd-resolved, Docker `--dns` or app resolver setting).
- Make sure UDP/TCP port 53 to the DNS server is not blocked.
