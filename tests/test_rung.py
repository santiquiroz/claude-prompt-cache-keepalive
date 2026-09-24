import os
import pathlib
import shutil
import subprocess
import tempfile
import time
import unittest

from keepalive_testing import REPO

MINUTES = "0.05"
LABEL = "2/6"
ALIVE_NAME = "2-6.alive"
TIMEOUT_SECONDS = 120


def powershell():
    return shutil.which("pwsh") or shutil.which("powershell")


def posix_bash():
    return shutil.which("bash") if os.name != "nt" else None


def ps1_command(state_dir):
    return [powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(REPO / "scripts" / "rung.ps1"),
            "-Minutes", MINUTES, "-Label", LABEL, "-StateDir", str(state_dir)]


def sh_command(state_dir):
    return [posix_bash(), (REPO / "scripts" / "rung.sh").as_posix(), MINUTES, LABEL, state_dir.as_posix()]


def run_watching_heartbeat(command, alive_file):
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
        saw_heartbeat = False
        deadline = time.monotonic() + TIMEOUT_SECONDS
        while process.poll() is None and time.monotonic() < deadline:
            saw_heartbeat = saw_heartbeat or alive_file.exists()
            time.sleep(0.05)
        process.kill()
        stdout, stderr = process.communicate()
    return process.returncode, stdout, stderr, saw_heartbeat


class RungContract:
    def command(self, state_dir):
        raise NotImplementedError

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.state_dir = pathlib.Path(temp.name) / "S"
        self.alive_file = self.state_dir / "rungs" / ALIVE_NAME

    def test_ticks_after_heart_beating_and_clears_its_alive_file(self):
        code, stdout, stderr, saw_heartbeat = run_watching_heartbeat(self.command(self.state_dir), self.alive_file)
        self.assertEqual(code, 0, stderr)
        self.assertTrue(stdout.startswith(f"KEEPALIVE_TICK {LABEL} "), stdout)
        self.assertTrue(saw_heartbeat)
        self.assertFalse(self.alive_file.exists())

    def test_a_stop_file_ends_it_with_stopped_and_clears_its_alive_file(self):
        self.state_dir.mkdir(parents=True)
        (self.state_dir / "stop").write_text("", encoding="utf-8")
        result = subprocess.run(self.command(self.state_dir), capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), f"KEEPALIVE_STOPPED {LABEL}")
        self.assertTrue((self.state_dir / "rungs").is_dir())
        self.assertFalse(self.alive_file.exists())


@unittest.skipUnless(os.name == "nt" and powershell(), "rung.ps1 uses kernel32 and runs on Windows only")
class PowerShellRungTest(RungContract, unittest.TestCase):
    def command(self, state_dir):
        return ps1_command(state_dir)


@unittest.skipUnless(posix_bash(), "rung.sh targets macOS and Linux; Windows runs rung.ps1")
class BashRungTest(RungContract, unittest.TestCase):
    def command(self, state_dir):
        return sh_command(state_dir)


if __name__ == "__main__":
    unittest.main()
