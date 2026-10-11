---
id: bad_config
title: Invalid configuration file
---
## Symptoms
A service refuses to start or reload after a config change: "syntax error", "invalid", "unknown directive", "unexpected end of file", "configuration file test failed", "Bad configuration option", "parse error", "could not load config", "emerg".

## Cause
A typo, missing semicolon or bracket, unknown option, wrong value type or wrong indentation in the configuration file.

## Fix
- Run the service's config test: `nginx -t`, `sshd -t`, `apachectl configtest`, or start Redis/Postgres in the foreground and read the first error.
- Fix the exact line and directive named in the error, or roll back to the last working config.
- Validate config files in CI before deploying.
