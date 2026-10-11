---
id: bad_config
title: Invalid configuration file
---
## Symptoms
A service refuses to start or reload after a config change: "syntax error", "invalid", "unknown directive", "unexpected end of file", "configuration file test failed", "Bad configuration option", "parse error", "could not load config", "emerg".

## Cause
A typo, missing semicolon or bracket, unknown option, wrong value type or wrong indentation in the configuration file.

## Fix
Run the service's config test (`nginx -t`, `sshd -t`, `apachectl configtest`, `named-checkconf`). Fix the line it names, or roll back to the last working config. Validate config in CI before deploying.
