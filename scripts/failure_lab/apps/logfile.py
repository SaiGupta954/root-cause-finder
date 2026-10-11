"""A service that writes its own log file under /var/log/app."""
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout)
log = logging.getLogger("billing")
log.info("billing service starting as uid=%d", os.getuid())
path = os.environ.get("LOG_FILE", "/var/log/app/billing.log")
handler = logging.FileHandler(path)
log.addHandler(handler)
log.info("file logging enabled at %s", path)
