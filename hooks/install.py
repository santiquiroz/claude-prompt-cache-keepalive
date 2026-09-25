"""Merge the keepalive hooks into ~/.claude/settings.json, leaving every other setting untouched."""
import argparse
import collections
import functools
import io
import json
import os
import pathlib
import shutil

HOOK_DIR = pathlib.Path(__file__).resolve().parent
ENTRIES = [
    ("UserPromptSubmit", "arm-nudge.mjs", {"timeout": 5}),
    ("Stop", "watchdog.mjs", {"timeout": 5, "async": True}),
]
INSTALL_BACKUP = ".json.bak-keepalive"
UNINSTALL_BACKUP = ".json.bak-keepalive-uninstall"
CASE_INSENSITIVE_PATHS = os.name == "nt"


def load(path):
    if not path.exists():
        return collections.OrderedDict()
    return json.load(io.open(path, encoding="utf-8"), object_pairs_hook=collections.OrderedDict)


def save(path, settings, backup_suffix):
    if path.exists():
        shutil.copyfile(path, path.with_suffix(backup_suffix))
    path.parent.mkdir(parents=True, exist_ok=True)
    io.open(path, "w", encoding="utf-8", newline="\n").write(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")


def script_path(hook_dir, script):
    return f"{pathlib.Path(hook_dir).as_posix()}/{script}"


def normalize_path(text):
    text = text.replace("\\", "/")
    return text.casefold() if CASE_INSENSITIVE_PATHS else text


def command_target(command):
    text = normalize_path(command).strip()
    if not text.startswith("node "):
        return None
    return text[len("node "):].strip().strip("\"'")


def is_our_hook(hook, hook_dir, script):
    return command_target(hook.get("command", "")) == normalize_path(script_path(hook_dir, script))


def already_installed(hooks, event, script, hook_dir):
    return any(is_our_hook(hook, hook_dir, script) for group in hooks.get(event, []) for hook in group.get("hooks", []))


def hook_entry(script, extra, hook_dir):
    command = collections.OrderedDict([("type", "command"), ("command", f'node "{script_path(hook_dir, script)}"')])
    command.update(extra)
    return collections.OrderedDict([("matcher", ""), ("hooks", [command])])


def install(path, hook_dir=HOOK_DIR):
    settings = load(path)
    hooks = settings.setdefault("hooks", collections.OrderedDict())
    added = []
    for event, script, extra in ENTRIES:
        if already_installed(hooks, event, script, hook_dir):
            continue
        hooks.setdefault(event, []).append(hook_entry(script, extra, hook_dir))
        added.append(f"{event}/{script}")
    if added:
        save(path, settings, INSTALL_BACKUP)
    return added


def group_without(group, is_ours):
    hooks = group.get("hooks", [])
    kept = [hook for hook in hooks if not is_ours(hook)]
    if len(kept) == len(hooks):
        return group
    if not kept:
        return None
    return collections.OrderedDict(group, hooks=kept)


def event_without(hooks, event, is_ours):
    groups = hooks.get(event, [])
    kept = [group for group in (group_without(group, is_ours) for group in groups) if group is not None]
    if kept == groups:
        return hooks
    if kept:
        return collections.OrderedDict(hooks, **{event: kept})
    return collections.OrderedDict((key, value) for key, value in hooks.items() if key != event)


def settings_with_hooks(settings, hooks):
    if hooks:
        return collections.OrderedDict(settings, hooks=hooks)
    return collections.OrderedDict((key, value) for key, value in settings.items() if key != "hooks")


def uninstall(path, hook_dir=HOOK_DIR):
    settings = load(path)
    hooks = settings.get("hooks", collections.OrderedDict())
    removed = []
    for event, script, _ in ENTRIES:
        remaining = event_without(hooks, event, functools.partial(is_our_hook, hook_dir=hook_dir, script=script))
        if remaining is not hooks:
            removed.append(f"{event}/{script}")
            hooks = remaining
    if removed:
        save(path, settings_with_hooks(settings, hooks), UNINSTALL_BACKUP)
    return removed


def report_install(path):
    added = install(path)
    return "installed: " + ", ".join(added) if added else "already installed: nothing to do"


def report_uninstall(path):
    removed = uninstall(path)
    return "uninstalled: " + ", ".join(removed) if removed else "not installed: nothing to do"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=pathlib.Path, default=pathlib.Path.home() / ".claude" / "settings.json")
    parser.add_argument("--uninstall", action="store_true", help="remove only the keepalive hooks (and the groups they leave empty)")
    args = parser.parse_args()
    print(report_uninstall(args.settings) if args.uninstall else report_install(args.settings))


if __name__ == "__main__":
    main()
