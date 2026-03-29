#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ -f venv/bin/activate ]]; then
  # shellcheck source=/dev/null
  source venv/bin/activate
fi
exec python3 check_missed_tasks.py
