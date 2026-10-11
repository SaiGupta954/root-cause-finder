---
id: ssh_bruteforce
title: Repeated SSH login failures (brute force)
---
## Symptoms
Many "Failed password for root/invalid user" lines from the same or a few IP addresses in a short time, "Invalid user", "authentication failure", "Too many authentication failures", "Connection closed by authenticating user", "maximum authentication attempts exceeded".

## Cause
An automated attacker or a misconfigured client is guessing usernames and passwords over SSH.

## Fix
- Block the source IPs (firewall rule or fail2ban).
- Disable password and root login: `PasswordAuthentication no`, `PermitRootLogin no`; use SSH keys.
- Check `last` and `lastb` for any successful logins from those IPs.
- Rate-limit or restrict SSH to known networks (VPN, bastion).
