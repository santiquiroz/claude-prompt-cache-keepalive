"""Merge the keepalive hooks into ~/.claude/settings.json, leaving every other setting untouched."""
import argparse
import collections
import io
import json
import pathlib
import shutil

HOOK_DIR = pathlib.Path(__file__).resolve().parent
ENTRIES = [
    ("UserPromptSubmit", "arm-nudge.mjs", {"timeout": 5}),
    ("Stop", "watchdog.mjs", {"timeout": 5, "async": True}),
]


def load(path):
    if not path.exists():
        return collections.OrderedDict()
    return json.load(io.open(path, encoding="utf-8"), object_pairs_hook=collections.OrderedDict)


def already_installed(hooks, event, script):
    return any(script in hook.get("command", "") for group in hooks.get(event, []) for hook in group.get("hooks", []))


def hook_entry(script, extra):
    command = collections.OrderedDict([("type", "command"), ("command", f"node {HOOK_DIR.as_posix()}/{script}")])
    command.update(extra)
    return collections.OrderedDict([("matcher", ""), ("hooks", [command])])


def install(path):
    settings = load(path)
    hooks = settings.setdefault("hooks", collections.OrderedDict())
    added = []
    for event, script, extra in ENTRIES:
        if already_installed(hooks, event, script):
            continue
        hooks.setdefault(event, []).append(hook_entry(script, extra))
        added.append(f"{event}/{script}")
    if not added:
        return []
    if path.exists():
        shutil.copyfile(path, path.with_suffix(".json.bak-keepalive"))
    path.parent.mkdir(parents=True, exist_ok=True)
    io.open(path, "w", encoding="utf-8", newline="\n").write(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
    return added


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=pathlib.Path, default=pathlib.Path.home() / ".claude" / "settings.json")
    added = install(parser.parse_args().settings)
    print("installed: " + ", ".join(added) if added else "already installed: nothing to do")


if __name__ == "__main__":
    main()
