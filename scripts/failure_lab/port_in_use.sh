#!/usr/bin/env bash
# Port already in use: a second server tries to bind a port another process holds.
#   nginx | redis | postgres_shared_net | python_api
source "$(dirname "$0")/lib.sh"
APPS="$LAB_DIR/apps:/apps:ro"

case "$VARIANT" in
  nginx)
    # A stray nginx started earlier in daemon mode still holds port 80 when the real one starts.
    run svc nginx:1.27-alpine sh -c "nginx && sleep 1 && exec nginx -g 'daemon off;'"
    wait_exit svc 30 ;;
  redis)
    run svc redis:7-alpine sh -c "redis-server --daemonize yes --logfile '' && sleep 1 && exec redis-server"
    wait_exit svc 30 ;;
  postgres_shared_net)
    run first -e POSTGRES_PASSWORD=lab postgres:16-alpine
    wait_for first "database system is ready to accept connections" 90
    docker run -d --label "rcf-lab=$CASE_ID" --name "$(cname svc)" --network "container:$(cname first)" \
      -e POSTGRES_PASSWORD=lab postgres:16-alpine >/dev/null
    wait_exit svc 90 ;;
  python_api)
    run svc -v "$APPS" python:3.12-alpine sh -c "python -u /apps/http_server.py 8000 metrics & sleep 2; exec python -u /apps/http_server.py 8000 orders-api"
    wait_for svc "Address in use|Address already in use" 30
    sleep 1 ;;
  *) log "unknown variant"; exit 2 ;;
esac
save_logs svc
