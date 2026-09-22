import argparse
import json
import pathlib

COLD_WRITE_THRESHOLD = 50_000


def assistant_usages(transcript):
    seen = set()
    for line in transcript.read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        message = entry.get("message") or {}
        usage = message.get("usage")
        if entry.get("type") != "assistant" or not usage or entry.get("isSidechain") or message.get("id") in seen:
            continue
        seen.add(message.get("id"))
        yield entry.get("timestamp", "?"), usage


RECENT_SECONDS = 3600


def latest_transcript(project_dir):
    files = sorted(pathlib.Path(project_dir).glob("*.jsonl"), key=lambda path: path.stat().st_mtime)
    if not files:
        raise SystemExit(f"no *.jsonl transcripts in {project_dir}")
    newest = files[-1]
    recent = [path for path in files if newest.stat().st_mtime - path.stat().st_mtime < RECENT_SECONDS]
    print(f"auditing {newest.name}")
    if len(recent) > 1:
        print(f"warning: {len(recent)} sessions changed in the last hour; pass this session's .jsonl explicitly")
    return newest


def main():
    parser = argparse.ArgumentParser(description="Show cache reads/writes of the main-thread turns of a Claude Code session.")
    parser.add_argument("path", help="session .jsonl, or the ~/.claude/projects/<project> folder to take the newest one")
    parser.add_argument("--last", type=int, default=10)
    args = parser.parse_args()
    target = pathlib.Path(args.path).expanduser()
    transcript = latest_transcript(target) if target.is_dir() else target
    rows = list(assistant_usages(transcript))[-args.last:]
    for timestamp, usage in rows:
        read = usage.get("cache_read_input_tokens", 0)
        written = usage.get("cache_creation_input_tokens", 0)
        verdict = "COLD (cache lost)" if written > COLD_WRITE_THRESHOLD and read < written else "warm"
        print(f"{timestamp}  read={read:>9,}  write={written:>9,}  {verdict}")


if __name__ == "__main__":
    main()
