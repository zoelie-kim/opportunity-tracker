#!/bin/bash
# One-time: install the LaunchAgent so schedules run after login, on an interval, and at calendar times.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PLIST_SRC="$ROOT/com.zoelie.opportunity-tracker.check-missed-tasks.plist"
AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST_DST="$AGENT_DIR/com.zoelie.opportunity-tracker.check-missed-tasks.plist"

chmod +x "$ROOT/run_check_missed_tasks.sh"
mkdir -p "$ROOT/logs"

cp "$PLIST_SRC" "$PLIST_DST"
UID_NUM="$(id -u)"
launchctl bootout "gui/${UID_NUM}" "$PLIST_DST" 2>/dev/null || true
if launchctl bootstrap "gui/${UID_NUM}" "$PLIST_DST" 2>/dev/null; then
  launchctl enable "gui/${UID_NUM}/com.zoelie.opportunity-tracker.check-missed-tasks" 2>/dev/null || true
else
  launchctl unload "$PLIST_DST" 2>/dev/null || true
  launchctl load -w "$PLIST_DST"
fi

echo "Installed: $PLIST_DST"
echo "Started. Logs: $ROOT/logs/check_missed_tasks.log"
