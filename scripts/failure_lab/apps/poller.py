"""Polls an HTTP endpoint every few seconds, like a health checker or sync job."""
import logging
import os
import sys
import time
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout)
log = logging.getLogger("sync")
url = os.environ.get("URL", "http://example.com/")
log.info("sync worker started, upstream=%s", url)
for attempt in range(1, int(os.environ.get("ROUNDS", "8")) + 1):
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            log.info("fetched %s status=%s bytes=%d", url, resp.status, len(resp.read()))
    except Exception as exc:
        log.error("sync attempt %d failed: %s", attempt, exc)
    time.sleep(2)
log.info("sync worker stopping")
