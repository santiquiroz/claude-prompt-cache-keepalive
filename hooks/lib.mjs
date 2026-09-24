import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync, rmSync } from 'node:fs'
import { join } from 'node:path'
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

function aliveFiles(rungsDir) {
  if (!existsSync(rungsDir)) return []
  return readdirSync(rungsDir)
    .filter(name => name.endsWith('.alive'))
    .map(name => {
      const path = join(rungsDir, name)
      const stat = statSync(path)
      return { name, path, mtimeMs: stat.mtimeMs, bornMs: stat.birthtimeMs || stat.ctimeMs }
    })
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
  const now = Date.now()
  return {
    dir,
    rungs,
    stopped: existsSync(join(dir, 'stop')),
    owner: readOwner(dir),
    live: rungs.filter(rung => now - rung.mtimeMs <= STALE_MS),
    stale: rungs.filter(rung => now - rung.mtimeMs > STALE_MS),
    armedAtMs: rungs.length ? Math.min(...rungs.map(rung => rung.bornMs)) : null,
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
  rmSync(join(dir, 'stop'), { force: true })
  rmSync(join(dir, 'DEAD'), { force: true })
  if (sessionId) writeFileSync(join(dir, 'owner'), sessionId, 'utf8')
  return dir
}

export function emit(output) {
  process.stdout.write(JSON.stringify(output))
  process.exit(0)
}
