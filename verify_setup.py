#!/usr/bin/env python3
"""
Plain-language check: are the files here, and is the Mac's scheduler watching this project?

Run from the project folder:
  python3 verify_setup.py

This does not send email or run scrapers — it only looks at files and (on a Mac) asks the system
whether your repeating task is registered.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
PLIST = REPO / "com.zoelie.opportunity-tracker.check-missed-tasks.plist"
LABEL = "com.zoelie.opportunity-tracker.check-missed-tasks"


def main() -> int:
    print()
    print("  Checking your opportunity-tracker setup…")
    print()

    ok = True

    # 1) Files
    need = [
        ("The small program that decides what to run", REPO / "check_missed_tasks.py"),
        ("The one-line launcher the Mac calls", REPO / "run_check_missed_tasks.sh"),
        ("The instructions file for the Mac scheduler", PLIST),
        ("The full scrape script", REPO / "run_all.py"),
    ]
    for label, p in need:
        if p.is_file():
            print(f"  ✓ {label} — found.")
        else:
            print(f"  ✗ {label} — missing: {p.name}")
            ok = False

    sh = REPO / "run_check_missed_tasks.sh"
    if sh.is_file() and not os.access(sh, os.X_OK):
        print("  ✗ The launcher script exists but isn’t marked “executable.” Run: chmod +x run_check_missed_tasks.sh")
        ok = False

    # 2) Plist syntax
    if PLIST.is_file():
        r = subprocess.run(["plutil", "-lint", str(PLIST)], capture_output=True, text=True)
        if r.returncode == 0:
            print("  ✓ The scheduler instructions file is valid.")
        else:
            print("  ✗ The scheduler instructions file has a problem (plutil -lint failed).")
            ok = False

    # 3) Mac only: is the job registered?
    if sys.platform != "darwin":
        print()
        print("  (You’re not on a Mac — skipping “is the Mac scheduler running this?”)")
        print()
        return 0 if ok else 1

    uid = os.getuid()
    target = f"gui/{uid}/{LABEL}"
    r = subprocess.run(["launchctl", "print", target], capture_output=True, text=True)
    if r.returncode == 0:
        print("  ✓ Your Mac’s built-in scheduler knows about this project’s repeating check.")
        print("    (That means: after you log in, it can wake up every so often and run the check.)")
    else:
        ok = False
        print("  ✗ Your Mac does not show this project’s repeating check yet.")
        print("    That usually means the one-time “install” step wasn’t run, or was run before something moved.")
        print()
        print("    What to do: open Terminal, go to this folder, and run:")
        print(f"      cd {REPO}")
        print("      ./install_launch_agent.sh")
        print()

    print()
    if ok:
        print("  All checks passed from here.")
        print("  Tip: after a day or two, peek at logs/check_missed_tasks.log to see lines from the checker.")
    else:
        print("  Something above needs fixing before the timer part is reliable.")
    print()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
