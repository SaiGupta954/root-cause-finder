# Shared helpers for the failure lab. Each case script sources this file.
#
# Rules: every log comes from a real container run. Scripts only start containers, cause the failure,
# and save `docker logs -t` output. They never write or edit log lines.
set -euo pipefail

LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$LAB_DIR/../.." && pwd)"
OUT_DIR="$ROOT/data/failure_lab"
mkdir -p "$OUT_DIR"

TYPE="$(basename "$0" .sh)"
VARIANT="${1:?usage: $0 <variant>}"
CASE_ID="${TYPE}_${VARIANT}"
NET="rcf-lab-$CASE_ID"

log() { echo "[$CASE_ID] $*" >&2; }

cleanup() {
  local ids
  ids="$(docker ps -aq --filter "label=rcf-lab=$CASE_ID")"
  [ -n "$ids" ] && docker rm -f $ids >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

docker network create "$NET" >/dev/null

# run NAME [docker run args...] IMAGE [cmd...]  -> starts a detached, labelled container on the case network
run() {
  local name="$1"; shift
  docker run -d --label "rcf-lab=$CASE_ID" --name "rcf-$CASE_ID-$name" --hostname "$name" --network "$NET" "$@" >/dev/null
}

cname() { echo "rcf-$CASE_ID-$1"; }

# wait_for NAME REGEX [SECONDS]  -> wait until the container's log matches
wait_for() {
  local name="$1" pattern="$2" limit="${3:-60}" i
  for ((i = 0; i < limit; i++)); do
    docker logs "$(cname "$name")" 2>&1 | grep -Eq "$pattern" && return 0
    sleep 1
  done
  log "timeout waiting for /$pattern/ in $name"
  return 1
}

# wait_exit NAME [SECONDS]  -> wait until the container has stopped
wait_exit() {
  local name="$1" limit="${2:-60}" i
  for ((i = 0; i < limit; i++)); do
    [ "$(docker inspect -f '{{.State.Running}}' "$(cname "$name")")" = "false" ] && return 0
    sleep 1
  done
  log "timeout waiting for $name to exit"
  return 1
}

# save_logs NAME  -> data/failure_lab/<case>.log, both streams, ordered by docker's timestamps
save_logs() {
  local out="$OUT_DIR/$CASE_ID.log"
  docker logs -t "$(cname "$1")" 2>&1 | LC_ALL=C sort -s -k1,1 > "$out"
  [ -s "$out" ] || { log "empty log"; return 1; }
  log "saved $(wc -l < "$out" | tr -d ' ') lines -> data/failure_lab/$CASE_ID.log"
}

# Small images used by several cases, built once.
build_image() {
  local tag="rcf-lab-$1"
  docker image inspect "$tag" >/dev/null 2>&1 || docker build -q -t "$tag" "$LAB_DIR/images/$1" >/dev/null
  echo "$tag"
}
