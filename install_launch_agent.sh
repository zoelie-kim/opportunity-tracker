#!/bin/bash
# Copies the LaunchAgent plist into ~/Library/LaunchAgents and loads it with launchctl
# so macOS runs check_missed_tasks on login, every 15 minutes, and at set clock times.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PLIST_SRC="$ROOT/com.zoelie.opportunity-tracker.check-missed-tasks.plist"
AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST_DST="$AGENT_DIR/com.zoelie.opportunity-tracker.check-missed-tasks.plist"

chmod +x "$ROOT/run_check_missed_tasks.sh"
mkdir -p "$ROOT/logs"

# Create/refresh the venv so launchd always uses the right Python with all packages installed.
# run_check_missed_tasks.sh activates venv/bin/activate when present.
#
# --clear rebuilds from scratch rather than "upgrading" in place. A venv hardcodes absolute
# paths in bin/activate and every bin/ shebang, so without it a venv left over from a previous
# repo location keeps pointing at the old path: activate silently falls back to system python
# and bin/pip dies with "bad interpreter".
echo "Setting up Python virtual environment..."
python3 -m venv --clear "$ROOT/venv"
"$ROOT/venv/bin/pip" install --upgrade pip --quiet
"$ROOT/venv/bin/pip" install -r "$ROOT/requirements.txt" --quiet
"$ROOT/venv/bin/python" -m playwright install chromium
echo "Virtual environment ready."

# The plist ships with a __REPO_ROOT__ placeholder rather than a hardcoded path, so the
# installed agent always points at wherever this repo actually lives. A verbatim copy here
# is what silently broke scheduling after the repo was moved: launchd kept running the old
# path, failing, and recreating a stray logs/ dir next to it.
sed "s|__REPO_ROOT__|$ROOT|g" "$PLIST_SRC" > "$PLIST_DST"
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
