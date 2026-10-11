#!/usr/bin/env bash
# Repeated SSH login failures: attacker containers guess passwords against sshd.
#   root | user_enum | many_ips
source "$(dirname "$0")/lib.sh"
SSHD="$(build_image sshd)"; CLIENT="$(build_image sshclient)"
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 -o NumberOfPasswordPrompts=1"

attack() {  # attack NAME "user1 user2 ..." TRIES
  run "$1" "$CLIENT" sh -c "for i in \$(seq 1 $3); do for u in $2; do sshpass -p guess\$i ssh $OPTS \$u@sshd true 2>/dev/null; done; done; true"
}

run sshd "$SSHD"
wait_for sshd "Server listening" 30
# Normal use first: a successful login by the deploy user.
# It stays running so attackers never reuse its IP address.
run legit "$CLIENT" sh -c "sshpass -p deploy-lab-pass-42 ssh $OPTS deploy@sshd 'uptime' >/dev/null 2>&1; sleep 600"
wait_for sshd "Accepted password for deploy" 30

case "$VARIANT" in
  root) attack attacker "root" 25; wait_exit attacker 180 ;;
  user_enum) attack attacker "admin oracle test postgres ubuntu git" 4; wait_exit attacker 180 ;;
  many_ips)
    attack attacker1 "root admin" 6; attack attacker2 "root ubuntu" 6; attack attacker3 "root test" 6
    wait_exit attacker1 180; wait_exit attacker2 180; wait_exit attacker3 180 ;;
  *) log "unknown variant"; exit 2 ;;
esac
sleep 1
save_logs sshd
