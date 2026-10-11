#!/usr/bin/env bash
# Invalid configuration file: the service refuses to start.
#   nginx_typo | nginx_semicolon | redis | postgres
source "$(dirname "$0")/lib.sh"

case "$VARIANT" in
  nginx_typo)
    run svc nginx:1.27-alpine sh -c "sed -i 's/listen       80;/listn       80;/' /etc/nginx/conf.d/default.conf && exec nginx -g 'daemon off;'"
    wait_exit svc 30 ;;
  nginx_semicolon)
    run svc nginx:1.27-alpine sh -c "sed -i 's/server_name  localhost;/server_name  localhost/' /etc/nginx/conf.d/default.conf && exec nginx -g 'daemon off;'"
    wait_exit svc 30 ;;
  redis)
    run svc redis:7-alpine sh -c "printf 'port 6379\nmaxmemory 512mbx\nappendonly yes\n' > /tmp/redis.conf && exec redis-server /tmp/redis.conf"
    wait_exit svc 30 ;;
  postgres)
    run svc -e POSTGRES_PASSWORD=lab postgres:16-alpine postgres -c shared_buffers=lots
    wait_exit svc 90 ;;
  *) log "unknown variant"; exit 2 ;;
esac
save_logs svc
