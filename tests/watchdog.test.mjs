import { test } from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, rmSync, utimesSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const HOOK = join(import.meta.dirname, '..', 'hooks', 'watchdog.mjs')
const TEN_MINUTES_AGO = new Date(Date.now() - 10 * 60 * 1000)

function makeDeadLadder(t, owner) {
  const home = mkdtempSync(join(tmpdir(), 'keepalive-test-'))
  t.after(() => rmSync(home, { recursive: true, force: true }))
  const dir = join(home, '.claude', 'keepalive', owner)
  const alive = join(dir, 'rungs', '3-6.alive')
  mkdirSync(join(dir, 'rungs'), { recursive: true })
  writeFileSync(join(dir, 'owner'), owner, 'utf8')
  writeFileSync(alive, '', 'utf8')
  utimesSync(alive, TEN_MINUTES_AGO, TEN_MINUTES_AGO)
  return { home, dir }
}

function runWatchdog(home, sessionId) {
  return spawnSync(process.execPath, [HOOK], {
    input: JSON.stringify({ session_id: sessionId }),
    encoding: 'utf8',
    env: { ...process.env, HOME: home, USERPROFILE: home },
  })
}

test('another session does not mark a dead ladder it does not own', t => {
  const { home, dir } = makeDeadLadder(t, 'A')
  const result = runWatchdog(home, 'OTHER')
  assert.equal(result.status, 0)
  assert.equal(result.stdout, '')
  assert.equal(existsSync(join(dir, 'DEAD')), false)
})

test('the owner session marks its dead ladder', t => {
  const { home, dir } = makeDeadLadder(t, 'A')
  const result = runWatchdog(home, 'A')
  assert.equal(result.status, 0)
  assert.match(result.stdout, /escalera caida/)
  assert.equal(existsSync(join(dir, 'DEAD')), true)
})
