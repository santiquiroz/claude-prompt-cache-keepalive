import json
import os
import pathlib
import tempfile
import unittest

from keepalive_testing import REPO, load_script, run_main

install = load_script("hooks/install.py")
HOOK_DIR = (REPO / "hooks").resolve().as_posix()
SPACED_HOOK_DIR = pathlib.Path("C:/Users/Juan Perez/.claude/skills/keeping-prompt-cache-warm/hooks")
UNINSTALL_BACKUP = ".json.bak-keepalive-uninstall"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def commands(settings, event):
    return [hook for group in settings["hooks"][event] for hook in group["hooks"]]


def ours(script, hook_dir=HOOK_DIR):
    return f'node "{hook_dir}/{script}"'


def group(*command_lines):
    return {"matcher": "", "hooks": [{"type": "command", "command": line} for line in command_lines]}


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
        self.assertEqual(commands(settings, "UserPromptSubmit"), [{"type": "command", "command": ours("arm-nudge.mjs"), "timeout": 5}])
        self.assertEqual(commands(settings, "Stop"), [{"type": "command", "command": ours("watchdog.mjs"), "timeout": 5, "async": True}])
        self.assertFalse(self.settings.with_suffix(".json.bak-keepalive").exists())

    def test_keeps_every_other_setting_and_backs_up_the_original(self):
        original = {"model": "opus", "hooks": {"Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "other"}]}]}, "theme": "dark"}
        self.write_settings(original)
        before = self.settings.read_text(encoding="utf-8")
        install.install(self.settings)
        settings = read_json(self.settings)
        self.assertEqual(list(settings), ["model", "hooks", "theme"])
        self.assertEqual([hook["command"] for hook in commands(settings, "Stop")], ["other", ours("watchdog.mjs")])
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

    def test_quotes_a_hook_path_that_contains_spaces(self):
        install.install(self.settings, SPACED_HOOK_DIR)
        settings = read_json(self.settings)
        self.assertEqual(commands(settings, "UserPromptSubmit")[0]["command"], ours("arm-nudge.mjs", SPACED_HOOK_DIR.as_posix()))
        self.assertEqual(commands(settings, "Stop")[0]["command"], ours("watchdog.mjs", SPACED_HOOK_DIR.as_posix()))

    def test_a_hook_of_another_tool_with_the_same_script_name_does_not_count_as_installed(self):
        self.write_settings({"hooks": {"Stop": [group("node /other/tool/watchdog.mjs")]}})
        added = install.install(self.settings)
        settings = read_json(self.settings)
        self.assertEqual(added, ["UserPromptSubmit/arm-nudge.mjs", "Stop/watchdog.mjs"])
        self.assertEqual([hook["command"] for hook in commands(settings, "Stop")], ["node /other/tool/watchdog.mjs", ours("watchdog.mjs")])

    def test_recognizes_an_earlier_unquoted_install_with_backslashes(self):
        windows_dir = HOOK_DIR.replace("/", "\\")
        self.write_settings({"hooks": {
            "UserPromptSubmit": [group(f"node {HOOK_DIR}/arm-nudge.mjs")],
            "Stop": [group(f"node {windows_dir}\\watchdog.mjs")],
        }})
        self.assertEqual(install.install(self.settings), [])

    @unittest.skipUnless(os.name == "nt", "paths are case-insensitive only on Windows")
    def test_ignores_path_case_on_windows(self):
        self.write_settings({"hooks": {
            "UserPromptSubmit": [group(ours("arm-nudge.mjs", HOOK_DIR.upper()))],
            "Stop": [group(ours("watchdog.mjs", HOOK_DIR.lower()))],
        }})
        self.assertEqual(install.install(self.settings), [])


class UninstallTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.settings = pathlib.Path(temp.name) / "settings.json"

    def write_settings(self, data):
        self.settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def test_restores_the_original_settings_and_backs_up_the_installed_ones(self):
        original = {"model": "opus", "hooks": {"Stop": [group("node /other/tool/watchdog.mjs")]}, "theme": "dark"}
        self.write_settings(original)
        install.install(self.settings)
        installed = self.settings.read_text(encoding="utf-8")
        removed = install.uninstall(self.settings)
        self.assertEqual(removed, ["UserPromptSubmit/arm-nudge.mjs", "Stop/watchdog.mjs"])
        self.assertEqual(read_json(self.settings), original)
        self.assertEqual(self.settings.with_suffix(UNINSTALL_BACKUP).read_text(encoding="utf-8"), installed)

    def test_drops_the_hooks_key_when_only_our_hooks_were_there(self):
        self.write_settings({"model": "opus"})
        install.install(self.settings)
        install.uninstall(self.settings)
        self.assertEqual(read_json(self.settings), {"model": "opus"})

    def test_keeps_other_hooks_that_share_a_group_with_ours(self):
        self.write_settings({"hooks": {"Stop": [group("other", f"node {HOOK_DIR}/watchdog.mjs")]}})
        self.assertEqual(install.uninstall(self.settings), ["Stop/watchdog.mjs"])
        self.assertEqual(read_json(self.settings), {"hooks": {"Stop": [group("other")]}})

    def test_keeps_empty_groups_it_did_not_empty(self):
        original = {"hooks": {"Stop": [{"matcher": "x", "hooks": []}, group(ours("watchdog.mjs"))], "PreToolUse": []}}
        self.write_settings(original)
        install.uninstall(self.settings)
        self.assertEqual(read_json(self.settings), {"hooks": {"Stop": [{"matcher": "x", "hooks": []}], "PreToolUse": []}})

    def test_changes_nothing_when_our_hooks_are_absent(self):
        self.write_settings({"hooks": {"Stop": [group("node /other/tool/watchdog.mjs")]}})
        before = self.settings.read_text(encoding="utf-8")
        self.assertEqual(install.uninstall(self.settings), [])
        self.assertEqual(self.settings.read_text(encoding="utf-8"), before)
        self.assertFalse(self.settings.with_suffix(UNINSTALL_BACKUP).exists())

    def test_leaves_a_missing_settings_file_missing(self):
        self.assertEqual(install.uninstall(self.settings), [])
        self.assertFalse(self.settings.exists())

    def test_cli_reports_what_it_uninstalled_then_that_there_is_nothing_to_do(self):
        install.install(self.settings)
        _, first, _ = run_main(install, "--uninstall", "--settings", str(self.settings))
        _, second, _ = run_main(install, "--uninstall", "--settings", str(self.settings))
        self.assertEqual(first.strip(), "uninstalled: UserPromptSubmit/arm-nudge.mjs, Stop/watchdog.mjs")
        self.assertEqual(second.strip(), "not installed: nothing to do")


if __name__ == "__main__":
    unittest.main()
