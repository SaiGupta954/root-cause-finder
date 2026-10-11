"""Connects to a backend by host name every few seconds, like a service talking to its database."""
import logging
import os
import socket
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout)
log = logging.getLogger("orders-api")
host, port = os.environ.get("DB_HOST", "example.com"), int(os.environ.get("DB_PORT", "80"))
log.info("orders-api starting, database at %s:%d", host, port)
for attempt in range(1, 9):
    try:
        with socket.create_connection((host, port), timeout=5):
            log.info("database connection ok")
    except OSError as exc:
        log.error("could not connect to database %s:%d (attempt %d): %s", host, port, attempt, exc)
    time.sleep(2)
