"""
Checks that files and the Mac scheduler hook are set up correctly.
Run: python3 -m unittest test_setup -v
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent
PLIST_NAME = "com.zoelie.opportunity-tracker.check-missed-tasks.plist"
LAUNCH_AGENT_LABEL = "com.zoelie.opportunity-tracker.check-missed-tasks"


class TestFilesAndScripts(unittest.TestCase):
    """These pass if the project folder has everything it needs."""

    def test_main_scripts_exist(self):
        self.assertTrue((REPO / "check_missed_tasks.py").is_file(), "Missing check_missed_tasks.py")
        self.assertTrue((REPO / "run_check_missed_tasks.sh").is_file(), "Missing run_check_missed_tasks.sh")
        self.assertTrue((REPO / "run_all.py").is_file(), "Missing run_all.py")
        self.assertTrue((REPO / "newsletter.py").is_file(), "Missing newsletter.py")
        self.assertTrue((REPO / "error_monitor.py").is_file(), "Missing error_monitor.py")

    def test_launch_agent_files_exist(self):
        self.assertTrue((REPO / PLIST_NAME).is_file(), f"Missing {PLIST_NAME}")
        self.assertTrue((REPO / "install_launch_agent.sh").is_file(), "Missing install_launch_agent.sh")

    def test_shell_launcher_is_executable(self):
        sh = REPO / "run_check_missed_tasks.sh"
        self.assertTrue(os.access(sh, os.X_OK), "run_check_missed_tasks.sh should be executable (chmod +x)")

    def test_plist_is_valid_xml(self):
        r = subprocess.run(
            ["plutil", "-lint", str(REPO / PLIST_NAME)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, r.stderr or r.stdout)


@unittest.skipUnless(sys.platform == "darwin", "LaunchAgent only applies on macOS")
class TestMacScheduler(unittest.TestCase):
    """On a Mac, checks whether Apple's scheduler knows about your job."""

    def test_launchd_knows_about_our_job(self):
        uid = os.getuid()
        target = f"gui/{uid}/{LAUNCH_AGENT_LABEL}"
        r = subprocess.run(
            ["launchctl", "print", target],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            r.returncode,
            0,
            "launchctl could not find your scheduled job. "
            f"You may need to run ./install_launch_agent.sh once. "
            f"(tried: launchctl print {target})\n"
            f"stderr: {r.stderr[:500]}",
        )


if __name__ == "__main__":
    unittest.main()
