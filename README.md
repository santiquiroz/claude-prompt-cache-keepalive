# keeping-prompt-cache-warm

An agent skill for [Claude Code](https://claude.com/claude-code) that keeps a session's prompt cache alive while you are away, so a large conversation does not have to be re-read from scratch when you come back.

## The problem

Claude Code caches the conversation prefix for **exactly 60 minutes** after the last model request. If you leave a long session idle for longer than that (overnight, a meeting, a long background job), the next message re-reads the whole context uncached: slow, and it burns usage quota.

## What does and does not work

Verified in the Claude Code VS Code extension on Windows, by reading the session transcript usage (`cache_read_input_tokens` vs `cache_creation_input_tokens`):

| Mechanism | Wakes an idle session? |
|---|---|
| Background `Bash`/`PowerShell` job (`run_in_background: true`) when it exits | **Yes** |
| `CronCreate` recurring job | **No**: fired 0 times in 8.5 hours |
| `ScheduleWakeup` | Only inside `/loop` |
| `Monitor` | Expires in 30-60 minutes |
| Subagents / workflows running in the background | Do **not** refresh the main thread cache; only their final notification wakes it |

A gap of 60 min 20 s was already enough to lose the cache, so there is no slack beyond the hour.

## How it works

The skill arms a **ladder of independent background timers** in one shot (not a chain, so one missed wake does not stop the rest). Each timer:

- sleeps until its scheduled minute, polling a `stop` file every minute;
- holds an OS sleep lock while waiting (Windows `SetThreadExecutionState`, macOS `caffeinate`, Linux `systemd-inhibit`);
- exits printing `KEEPALIVE_TICK`, whose completion notification wakes the model for a one-line, tool-free reply that refreshes the cache.

## Install

```bash
git clone https://github.com/santiquiroz/claude-prompt-cache-keepalive ~/.claude/skills/keeping-prompt-cache-warm
```

Then wire the hooks so you never have to ask for it:

```bash
python ~/.claude/skills/keeping-prompt-cache-warm/hooks/install.py
```

From then on, saying "I'm going to sleep" (or "me voy a dormir", "afk", "back in 2 hours") is enough: the ladder goes up in that turn, and your next message takes it down.

The wake-on-exit behavior was verified in the VS Code extension. In a terminal session, arm a 2-minute test rung first and audit it with `cache_audit.py` before leaving.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/plan.py` | Minutes at which each rung fires (`--hours`, `--every` ≤ 50, `--first`) |
| `scripts/rung.ps1` / `scripts/rung.sh` | One background timer with stop file and sleep lock |
| `scripts/cache_audit.py` | Reads a session transcript and flags turns that lost the cache |
| `hooks/arm-nudge.mjs` | `UserPromptSubmit`: arms the ladder on a leaving phrase, stops it when you return |
| `hooks/watchdog.mjs` | `Stop`: flags rungs that stopped heart-beating (reload, update, forced sleep) |
| `hooks/install.py` | Merges both hooks into `~/.claude/settings.json` without touching the rest |

## Limits

- The editor/terminal session must stay open: a window reload, an extension auto-update or an OS restart kills the timers.
- Closing a laptop lid or forcing sleep overrides the wake lock.
- The cache is best effort; a model fallback or an auto-compaction changes the prefix.
- Cost: each tick is a cache read (~0.1× the context); a cold 1-hour cache write is ~2×. Beyond ~20 ticks it is cheaper to let it expire, so size the ladder to the real absence.

## License

MIT
