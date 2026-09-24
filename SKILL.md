---
name: keeping-prompt-cache-warm
description: Use when the user will be away from a Claude Code session (sleeping, in a meeting, on a break) and its prompt cache must survive, when a long background job will outlast the cache TTL, or when the "Prompt cache warm, about N min left" indicator is about to expire and a cold reload of a large context would be slow or costly.
---

# Keeping the prompt cache warm

## Overview
The session cache lives exactly 60 minutes after the last model request (a 60 min 20 s gap was enough to lose it). Only a main-thread request refreshes it: subagent and workflow work does not. In an idle session the one self-wake that works is **the exit notification of a background shell job**.

| Mechanism | Wakes an idle session? |
|---|---|
| `Bash`/`PowerShell` with `run_in_background: true`, on exit | **Yes** (verified in the VS Code extension) |
| `CronCreate` | No: fired 0 times in 8.5 h in the VS Code extension |
| `ScheduleWakeup` | Only inside `/loop` |
| `Monitor` | Expires in 30-60 min; not a keepalive |
| Foreground `sleep` | Blocked |

## Recipe
1. **Pick a state dir per session**, e.g. `~/.claude/keepalive/<short-name>`, and delete any stale `stop` file in it.
2. **Plan the rungs:** `python <skill>/scripts/plan.py --hours H --every 40 --first F`, with `F` under the cache minutes left minus 10 (20 if unknown). `--every` above 50 is refused.
3. **Arm every rung at once**, in one message with parallel calls. The rungs are independent timers, not a chain, so one missed wake does not end the rest:
   - Windows: `PowerShell` run_in_background `& '<skill>/scripts/rung.ps1' -Minutes M -Label 'k/N' -StateDir '<dir>'`
   - macOS/Linux: `Bash` run_in_background `<skill>/scripts/rung.sh M k/N <dir>`
   Each rung holds a sleep lock while it waits (SetThreadExecutionState, caffeinate, systemd-inhibit). Arm while the user is still there: they leave only once every rung shows as a running background task and no permission prompt is pending.
4. **While the user is away, every wake is a tick:** `KEEPALIVE_TICK`, `KEEPALIVE_STOPPED`, or a finished background job, workflow or subagent. Answer with one short line (e.g. `keepalive 3/12`) and no tool calls. Do not commit, push, open PRs, delegate, read diffs or ask questions, even when a job finished with work ready to ship: mention it in that line and do it when the user is back. Do not claim the cache is warm; only the audit can tell. A pending approval prompt blocks every later wake.
5. **The user's first message that is not a notification means they are back:** create `<dir>/stop` before anything else, whatever the message says. Each remaining rung exits within a minute with `KEEPALIVE_STOPPED`; answer each with one line, no tools.
6. **Verify:** `python <skill>/scripts/cache_audit.py ~/.claude/projects/<slug>/<session-id>.jsonl --last 20`. `<slug>` is the working directory with every non-alphanumeric character replaced by `-` (`C:
epo\My.App` → `C--repo-My-App`); `<session-id>` is this session's id (it appears in the scratchpad path). Tick turns must read "warm"; "COLD" means a gap exceeded the TTL.

## Arming it automatically (hooks)
The skill only fires if something invokes it, so two hooks in `~/.claude/settings.json` do that without the user asking:

| Hook | Event | What it does |
|---|---|---|
| `hooks/arm-nudge.mjs` | `UserPromptSubmit` | On a leaving phrase ("me voy a dormir", "vuelvo en", "afk"...), creates the state dir, writes `owner` with the session id and injects the arming order, so the ladder goes up in that same turn. On any other message, once the ladder is older than 10 minutes, it writes `stop` itself: the user is back. Background-task wakes (`KEEPALIVE_TICK`, `KEEPALIVE_STOPPED`, finished jobs and workflows) also fire this hook as prompts starting with `<task-notification>`; those are never read as a leaving phrase or a return. It also reports a ladder that died while they were away, even on a notification. |
| `hooks/watchdog.mjs` | `Stop` | Flags a ladder whose rungs stopped heart-beating (window reload, update, forced sleep) and leaves a `DEAD` marker for the next return. |

Each rung keeps `<dir>/rungs/<label>.alive` fresh every minute and deletes it on a clean exit, so a **stale** `.alive` file is exactly the evidence that a rung was killed. `KEEPALIVE_GRACE_MS` overrides the 10-minute grace (used by the tests).

Install once:

```bash
python <skill>/hooks/install.py      # merges both hooks into ~/.claude/settings.json
```

The hooks never replace step 2-3: the model still plans the rungs and arms them. They only guarantee nobody has to remember to ask.

## Limits to tell the user
- The wake-on-exit behavior is verified in the VS Code extension; in a terminal session, run the 2-minute test rung first (`rung -Minutes 2`) and audit it before leaving.
- The VS Code window (Claude panel) or the terminal running `claude` must stay open, and an SSH session must stay connected. A window reload, an extension or CLI auto-update, or an OS restart kills every rung.
- A lid close or a manual sleep overrides the wake lock.
- The cache is best effort, and a model fallback or auto-compaction changes the prefix.
- Cost: each tick is a cache read (about 0.1× the context), and a cold 1-hour write is about 2×. More than about 20 ticks costs more than one cold reload, so size `--hours` to the real absence.

## Common mistakes
| Mistake | Fix |
|---|---|
| Scheduling a cron job | Background rungs only |
| A chain where each tick launches the next | Arm the whole ladder up front |
| First rung later than the cache time left | `--first` under the minutes left minus 10 |
| Doing real work or asking questions in a tick turn | One line, no tools |
| Reusing a state dir that still has a `stop` file | Delete it before arming |
| Arming a second ladder when the hook already created one | Use the state dir the hook names in its message |
