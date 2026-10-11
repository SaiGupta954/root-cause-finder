#!/usr/bin/env bash
# Service stuck in a restart loop: supervisord (or docker's restart policy) keeps restarting a process that exits.
#   missing_env | missing_module | segfault | docker_restart
source "$(dirname "$0")/lib.sh"
APPS="$LAB_DIR/apps:/apps:ro"

case "$VARIANT" in
  missing_env)
    run svc -v "$APPS" -e APP_CMD="python -u /apps/needs_env.py" "$(build_image supervisor)"
    wait_for svc "gave up" 90 ;;
  missing_module)
    run svc -e APP_CMD="python -u -c 'import requests_oauthlib'" "$(build_image supervisor)"
    wait_for svc "gave up" 90 ;;
  segfault)
    run svc -e APP_CMD="python -u -c 'import ctypes; print(\"render worker ready\"); ctypes.string_at(0)'" "$(build_image supervisor)"
    wait_for svc "gave up" 90 ;;
  docker_restart)
    run svc --restart on-failure:5 -e PORT=8080 node:22-alpine \
      node -e "console.log('api: loading config from /etc/api/config.json'); require('/etc/api/config.json')"
    for _ in $(seq 1 60); do
      [ "$(docker inspect -f '{{.RestartCount}}' "$(cname svc)")" -ge 5 ] && [ "$(docker inspect -f '{{.State.Running}}' "$(cname svc)")" = false ] && break
      sleep 2
    done ;;
  *) log "unknown variant"; exit 2 ;;
esac
save_logs svc
