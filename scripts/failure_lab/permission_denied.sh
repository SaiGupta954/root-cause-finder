#!/usr/bin/env bash
# Permission denied: a process lacks rights on a file or directory it needs.
#   nginx_root | app_logfile | postgres_datadir | static_upload
source "$(dirname "$0")/lib.sh"
APPS="$LAB_DIR/apps:/apps:ro"

case "$VARIANT" in
  nginx_root)
    run svc nginx:1.27-alpine sh -c "chmod 700 /usr/share/nginx/html && exec nginx -g 'daemon off;'"
    wait_for svc "start worker process" 30
    for p in / /index.html /about.html /; do docker exec "$(cname svc)" wget -q -O /dev/null "http://127.0.0.1$p" || true; done
    sleep 1 ;;
  app_logfile)
    run svc -v "$APPS" python:3.12-alpine sh -c "mkdir -p /var/log/app && adduser -D -u 1000 billing && \
      su billing -c 'python -u /apps/logfile.py'"
    wait_exit svc 30 ;;
  postgres_datadir)
    run svc --user 70:70 -e POSTGRES_PASSWORD=lab --mount type=tmpfs,destination=/srv/pgdata,tmpfs-mode=0755 \
      -e PGDATA=/srv/pgdata/data postgres:16-alpine
    wait_exit svc 60 ;;
  static_upload)
    run svc -v "$APPS" python:3.12-alpine sh -c "mkdir -p /srv/uploads && chmod 555 /srv/uploads && adduser -D -u 1001 web && \
      su web -c 'OUT=/srv/uploads/report.jsonl python -u /apps/writer.py'"
    wait_exit svc 60 ;;
  *) log "unknown variant"; exit 2 ;;
esac
save_logs svc
