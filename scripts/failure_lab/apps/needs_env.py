"""A web worker that needs DATABASE_URL to start."""
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout)
log = logging.getLogger("worker")
log.info("worker booting, pid=%d", os.getpid())
db_url = os.environ["DATABASE_URL"]
log.info("connected to %s", db_url)
