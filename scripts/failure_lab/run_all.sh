#!/usr/bin/env bash
# Run every failure-lab case (or only the ones named) and save logs to data/failure_lab/.
#   ./scripts/failure_lab/run_all.sh                 # all cases in labels.json
#   ./scripts/failure_lab/run_all.sh disk_full_redis # one case
set -uo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
LABELS="$DIR/../../data/failure_lab/labels.json"
cases=("$@")
if [ ${#cases[@]} -eq 0 ]; then
  while IFS= read -r c; do cases+=("$c"); done < <(python3 -c "import json,sys; [print(c['case']) for c in json.load(open(sys.argv[1]))]" "$LABELS")
fi
failed=()
for c in "${cases[@]}"; do
  script="" variant=""
  for t in disk_full dns_failure crash_loop permission_denied port_in_use out_of_memory bad_config ssh_bruteforce; do
    if [[ "$c" == "${t}_"* ]]; then script="$DIR/$t.sh"; variant="${c#"${t}_"}"; fi
  done
  [ -n "$script" ] || { echo "unknown case $c"; failed+=("$c"); continue; }
  "$script" "$variant" || failed+=("$c")
done
echo "done: $(( ${#cases[@]} - ${#failed[@]} ))/${#cases[@]} cases saved"
[ ${#failed[@]} -eq 0 ] || { echo "failed: ${failed[*]}"; exit 1; }
