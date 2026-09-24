import json
import pathlib
import tempfile
import unittest

from keepalive_testing import REPO, load_script, run_main

install = load_script("hooks/install.py")
HOOK_DIR = (REPO / "hooks").resolve().as_posix()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def commands(settings, event):
    return [hook for group in settings["hooks"][event] for hook in group["hooks"]]


class InstallTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.settings = pathlib.Path(temp.name) / "nested" / "settings.json"

    def write_settings(self, data):
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def test_creates_the_settings_file_with_both_hooks(self):
        added = install.install(self.settings)
        settings = read_json(self.settings)
        self.assertEqual(added, ["UserPromptSubmit/arm-nudge.mjs", "Stop/watchdog.mjs"])
        self.assertEqual(commands(settings, "UserPromptSubmit"), [{"type": "command", "command": f"node {HOOK_DIR}/arm-nudge.mjs", "timeout": 5}])
        self.assertEqual(commands(settings, "Stop"), [{"type": "command", "command": f"node {HOOK_DIR}/watchdog.mjs", "timeout": 5, "async": True}])
        self.assertFalse(self.settings.with_suffix(".json.bak-keepalive").exists())

    def test_keeps_every_other_setting_and_backs_up_the_original(self):
        original = {"model": "opus", "hooks": {"Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "other"}]}]}, "theme": "dark"}
        self.write_settings(original)
        before = self.settings.read_text(encoding="utf-8")
        install.install(self.settings)
        settings = read_json(self.settings)
        self.assertEqual(list(settings), ["model", "hooks", "theme"])
        self.assertEqual([hook["command"] for hook in commands(settings, "Stop")], ["other", f"node {HOOK_DIR}/watchdog.mjs"])
        self.assertEqual(self.settings.with_suffix(".json.bak-keepalive").read_text(encoding="utf-8"), before)

    def test_a_second_run_changes_nothing(self):
        install.install(self.settings)
        before = self.settings.read_text(encoding="utf-8")
        self.assertEqual(install.install(self.settings), [])
        self.assertEqual(self.settings.read_text(encoding="utf-8"), before)
        self.assertFalse(self.settings.with_suffix(".json.bak-keepalive").exists())

    def test_cli_reports_what_it_installed_then_that_there_is_nothing_to_do(self):
        _, first, _ = run_main(install, "--settings", str(self.settings))
        _, second, _ = run_main(install, "--settings", str(self.settings))
        self.assertEqual(first.strip(), "installed: UserPromptSubmit/arm-nudge.mjs, Stop/watchdog.mjs")
        self.assertEqual(second.strip(), "already installed: nothing to do")


if __name__ == "__main__":
    unittest.main()
