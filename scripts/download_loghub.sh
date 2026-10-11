#!/usr/bin/env bash
# Download public Loghub logs into data/. Cite Loghub in the README (see data/README.md).
#   ./scripts/download_loghub.sh          # 2k-line samples from GitHub (fast)
#   ./scripts/download_loghub.sh --full   # full Linux (25,567 lines) and OpenSSH logs from Zenodo
set -euo pipefail
cd "$(dirname "$0")/../data"

base=https://raw.githubusercontent.com/logpai/loghub/master
curl -fsSL "$base/Linux/Linux_2k.log" -o Linux_2k.log
curl -fsSL "$base/OpenSSH/OpenSSH_2k.log" -o OpenSSH_2k.log
echo "Saved data/Linux_2k.log and data/OpenSSH_2k.log"

if [[ "${1:-}" == "--full" ]]; then
  zen=https://zenodo.org/records/8196385/files
  curl -fL "$zen/Linux.tar.gz?download=1" -o Linux.tar.gz && tar -xzf Linux.tar.gz
  curl -fL "$zen/SSH.tar.gz?download=1" -o SSH.tar.gz && tar -xzf SSH.tar.gz
  rm -f Linux.tar.gz SSH.tar.gz
  echo "Extracted full logs into data/"
fi
