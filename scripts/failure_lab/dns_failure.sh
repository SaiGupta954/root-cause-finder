#!/usr/bin/env bash
# Wrong DNS server: the resolver points at a container that runs no DNS server.
# (A made-up outside address does not work under Colima/Lima: its network answers all outgoing DNS itself.)
#   wget | python_http | db_connect | nginx_resolver
source "$(dirname "$0")/lib.sh"
APPS="$LAB_DIR/apps:/apps:ro"
run not-a-dns-server alpine:3.20 sleep 600
BAD_DNS="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$(cname not-a-dns-server)")"
log "wrong DNS server: $BAD_DNS"

case "$VARIANT" in
  wget)
    run svc --dns "$BAD_DNS" alpine:3.20 sh -c 'echo "backup-agent: starting upload run"; for i in 1 2 3 4 5; do wget -q -T 5 -O /dev/null http://example.com/upload && echo "upload $i ok" || echo "upload $i failed"; sleep 1; done'
    wait_exit svc 120 ;;
  python_http)
    run svc --dns "$BAD_DNS" -v "$APPS" -e URL=http://example.com/ -e ROUNDS=6 python:3.12-slim python -u /apps/poller.py
    wait_exit svc 180 ;;
  db_connect)
    run svc --dns 127.0.0.1 -v "$APPS" -e DB_HOST=example.com python:3.12-slim python -u /apps/resolver.py
    wait_exit svc 120 ;;
  nginx_resolver)
    cat > "$OUT_DIR/.nginx_resolver.conf" <<CONF
server {
    listen 80;
    resolver $BAD_DNS valid=10s;
    resolver_timeout 3s;
    location / {
        set \$upstream http://example.com;
        proxy_pass \$upstream;
    }
}
CONF
    run svc -v "$OUT_DIR/.nginx_resolver.conf:/etc/nginx/conf.d/default.conf:ro" nginx:1.27-alpine
    wait_for svc "start worker process" 30
    for i in 1 2 3 4 5; do docker exec "$(cname svc)" wget -q -T 8 -O /dev/null "http://127.0.0.1/item/$i" || true; done
    rm -f "$OUT_DIR/.nginx_resolver.conf" ;;
  *) log "unknown variant"; exit 2 ;;
esac
save_logs svc
