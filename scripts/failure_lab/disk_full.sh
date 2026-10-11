#!/usr/bin/env bash
# Disk full: give a service a tiny filesystem and let it fill up.
#   postgres | redis | nginx | exporter
source "$(dirname "$0")/lib.sh"
APPS="$LAB_DIR/apps:/apps:ro"

case "$VARIANT" in
  postgres)
    run svc -e POSTGRES_PASSWORD=lab --mount type=tmpfs,destination=/var/lib/postgresql/data,tmpfs-size=80000000 postgres:16-alpine
    wait_for svc "database system is ready to accept connections" 90
    sleep 3
    docker exec "$(cname svc)" psql -U postgres -c "CREATE TABLE events AS SELECT g AS id, md5(g::text) AS h FROM generate_series(1, 1000) g;" >/dev/null
    docker exec "$(cname svc)" psql -U postgres -c "INSERT INTO events SELECT g, repeat(md5(g::text), 30) FROM generate_series(1, 400000) g;" >/dev/null 2>&1 || true
    sleep 2 ;;
  redis)
    run svc --mount type=tmpfs,destination=/data,tmpfs-size=6000000 redis:7-alpine redis-server --appendonly yes --dir /data
    wait_for svc "Ready to accept connections" 30
    docker exec "$(cname svc)" redis-benchmark -q -t set -d 20000 -n 2000 -r 100000 >/dev/null 2>&1 || true
    sleep 12 ;;  # redis retries the AOF write every second and logs each failure
  nginx)
    run svc --mount type=tmpfs,destination=/var/log/web,tmpfs-size=300000 nginx:1.27-alpine \
      sh -c "sed -i 's#access_log .*#access_log /var/log/web/access.log main;#' /etc/nginx/nginx.conf && exec nginx -g 'daemon off;'"
    wait_for svc "start worker process" 30
    docker exec "$(cname svc)" sh -c 'for i in $(seq 1 4000); do wget -q -O /dev/null "http://127.0.0.1/?page=$i&q=$(head -c 30 /dev/urandom | base64 | tr -dc a-z)"; done' || true
    sleep 1 ;;
  exporter)
    run svc -v "$APPS" --mount type=tmpfs,destination=/data,tmpfs-size=3000000 python:3.12-alpine python -u /apps/writer.py
    wait_exit svc 120 ;;
  *) log "unknown variant"; exit 2 ;;
esac
save_logs svc
