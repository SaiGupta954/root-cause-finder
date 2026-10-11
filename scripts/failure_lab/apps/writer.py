"""A small batch job: writes records to /data and logs what it does."""
import json
import logging
import os
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout)
log = logging.getLogger("exporter")
path = os.environ.get("OUT", "/data/export.jsonl")
log.info("exporter starting, writing to %s", path)
failures = 0
for batch in range(1, 10_000):
    try:
        with open(path, "a") as fh:
            for i in range(500):
                fh.write(json.dumps({"batch": batch, "row": i, "payload": "x" * 400}) + "\n")
        log.info("batch %d written (500 rows)", batch)
        failures = 0
    except OSError as exc:
        failures += 1
        log.error("batch %d failed: %s", batch, exc)
        if failures >= 5:
            log.critical("giving up after %d failed batches", failures)
            sys.exit(1)
    time.sleep(0.2)
