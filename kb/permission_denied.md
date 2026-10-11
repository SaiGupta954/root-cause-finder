---
id: permission_denied
title: Permission denied on a file or directory
---
## Symptoms
"Permission denied" (EACCES, errno 13) or "Operation not permitted" (EPERM) when a service opens, reads or writes a file, directory or socket. "could not open file", "failed to open log", "cannot create directory". The service fails to start or a feature stops working.

## Cause
The process user lacks rights on the path: wrong owner or mode after a deploy or copy, a service running as a different user, a read-only mount, or SELinux/AppArmor denials.

## Fix
- Find the path in the error and check owner and mode along the whole path: `namei -l <path>`.
- Check which user the service runs as (`ps -o user= -p <pid>`).
- Fix ownership or mode with `chown`/`chmod` (never chmod 777), or run the service as the right user.
- If permissions look right, check SELinux (`ausearch -m avc`) or AppArmor denials.
