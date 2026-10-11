#!/usr/bin/env bash
# Out of memory: a process needs more memory than its limit allows.
#   cgroup_kill | python_memoryerror | redis_maxmemory | node_heap
source "$(dirname "$0")/lib.sh"
APPS="$LAB_DIR/apps:/apps:ro"

case "$VARIANT" in
  cgroup_kill)
    run svc -v "$APPS" --memory 96m --memory-swap 96m python:3.12-slim bash -c "python -u /apps/alloc.py; exit \$?"  # child of bash, so bash reports the kill
    wait_exit svc 60 ;;
  python_memoryerror)
    run svc -v "$APPS" python:3.12-alpine sh -c "ulimit -v 250000; python -u /apps/alloc.py"
    wait_exit svc 60 ;;
  redis_maxmemory)
    # A session writer that logs only the replies that are not OK.
    run svc redis:7-alpine sh -c 'redis-server --maxmemory 3mb --maxmemory-policy noeviction --daemonize yes --logfile /dev/stdout && sleep 1 &&
      echo "session-writer: storing sessions" && v=$(printf "%10000s" | tr " " x) &&
      for i in $(seq 1 400); do out=$(redis-cli set session:$i "$v"); [ "$out" = OK ] || echo "session-writer: set session:$i failed: $out"; done; sleep 1'
    wait_exit svc 90 ;;
  node_heap)
    run svc node:22-alpine node --max-old-space-size=48 -e "console.log('cache warmer: loading product catalog'); const c=[]; let n=0; setInterval(()=>{ for(let i=0;i<20000;i++) c.push({id:n++, name:'product '+n, tags:['a','b','c']}); if(n%200000===0) console.log('cached', n, 'products'); }, 1)"
    wait_exit svc 120 ;;
  *) log "unknown variant"; exit 2 ;;
esac
save_logs svc
