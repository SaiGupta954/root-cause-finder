"""A report builder that keeps all rows in memory (the leak)."""
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout)
log = logging.getLogger("report-builder")
log.info("building monthly report")
rows = []
for chunk in range(1, 100_000):
    rows.append(bytearray(10 * 1024 * 1024))
    if chunk % 2 == 0:
        log.info("loaded %d MB of rows", chunk * 10)
