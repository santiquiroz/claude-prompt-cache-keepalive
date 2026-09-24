import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync, rmSync } from 'node:fs'
import { join, posix, win32 } from 'node:path'
import { homedir } from 'node:os'

export const ROOT = join(homedir(), '.claude', 'keepalive')
export const STALE_MS = 3 * 60 * 1000

export function readStdin() {
  return new Promise(resolve => {
    let data = ''
    process.stdin.setEncoding('utf8')
    process.stdin.on('data', chunk => { data += chunk })
    process.stdin.on('end', () => resolve(data))
    setTimeout(() => resolve(data), 2000).unref?.()
  })
}

export function parsePayload(raw) {
  try { return JSON.parse(raw) } catch { return {} }
}

// UserPromptSubmit also fires for background-task wakes (ticks, STOPPED, workflows), which are not the user.
export function isSystemNotification(prompt) {
  return String(prompt ?? '').trimStart().startsWith('<task-notification>')
}

function aliveNames(rungsDir) {
  return readdirSync(rungsDir).filter(name => name.endsWith('.alive'))
}

// A rung deletes its .alive on a clean exit, possibly between readdir and stat.
function statRung(rungsDir, name, stat) {
  const path = join(rungsDir, name)
  try {
    const info = stat(path)
    return { name, path, mtimeMs: info.mtimeMs, bornMs: info.birthtimeMs || info.ctimeMs }
  } catch (error) {
    if (error?.code === 'ENOENT') return null
    throw error
  }
}

export function aliveFiles(rungsDir, stat = statSync) {
  if (!existsSync(rungsDir)) return []
  return aliveNames(rungsDir).map(name => statRung(rungsDir, name, stat)).filter(Boolean)
}

export function listLadders() {
  if (!existsSync(ROOT)) return []
  return readdirSync(ROOT, { withFileTypes: true })
    .filter(entry => entry.isDirectory())
    .map(entry => describeLadder(join(ROOT, entry.name)))
    .filter(ladder => ladder.rungs.length > 0)
}

export function describeLadder(dir) {
  const rungs = aliveFiles(join(dir, 'rungs'))
  return {
    dir,
    rungs,
    stopped: existsSync(join(dir, 'stop')),
    owner: readOwner(dir),
    ...summarizeRungs(rungs, Date.now()),
  }
}

export function summarizeRungs(rungs, now) {
  const live = rungs.filter(rung => now - rung.mtimeMs <= STALE_MS)
  const stale = rungs.filter(rung => now - rung.mtimeMs > STALE_MS)
  return {
    live,
    stale,
    dead: stale.length > 0 && live.length === 0,
    armedAtMs: live.length ? Math.min(...live.map(rung => rung.bornMs)) : null,
    lastBeatMs: rungs.length ? Math.max(...rungs.map(rung => rung.mtimeMs)) : null,
  }
}

function readOwner(dir) {
  const path = join(dir, 'owner')
  if (!existsSync(path)) return null
  try { return readFileSync(path, 'utf8').trim() } catch { return null }
}

// Several sessions share ROOT: a ladder without owner, or a session without id, belongs to nobody.
export function ownedBy(ladder, sessionId) {
  return Boolean(sessionId) && ladder.owner === sessionId
}

export function createStateDir(sessionId) {
  const slug = (sessionId || 'session').replace(/[^0-9a-zA-Z]/g, '').slice(0, 8) || 'session'
  const dir = join(ROOT, slug)
  mkdirSync(join(dir, 'rungs'), { recursive: true })
  clearRungs(join(dir, 'rungs'))
  rmSync(join(dir, 'stop'), { force: true })
  rmSync(join(dir, 'DEAD'), { force: true })
  if (sessionId) writeFileSync(join(dir, 'owner'), sessionId, 'utf8')
  return dir
}

// Leftover .alive files from a killed ladder would make the new one look dead or old enough to stop.
function clearRungs(rungsDir) {
  for (const name of aliveNames(rungsDir)) rmSync(join(rungsDir, name), { force: true })
}

export function rungShell(platform) {
  return platform === 'win32' ? 'PowerShell' : 'Bash'
}

export function rungCommand(platform, skillDir, stateDir) {
  if (platform === 'win32') {
    return `& '${win32.join(skillDir, 'scripts', 'rung.ps1')}' -Minutes M -Label 'k/N' -StateDir '${stateDir}'`
  }
  return `bash '${posix.join(skillDir, 'scripts', 'rung.sh')}' M 'k/N' '${stateDir}'`
}

export function emit(output) {
  process.stdout.write(JSON.stringify(output))
  process.exit(0)
}
