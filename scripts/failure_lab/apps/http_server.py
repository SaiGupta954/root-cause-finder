"""A tiny HTTP API on the given port."""
import http.server
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout)
log = logging.getLogger(sys.argv[2] if len(sys.argv) > 2 else "api")
port = int(sys.argv[1])
log.info("starting on port %d", port)
server = http.server.HTTPServer(("0.0.0.0", port), http.server.SimpleHTTPRequestHandler)
log.info("listening on 0.0.0.0:%d", port)
server.serve_forever()
