import { test } from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, readdirSync, rmSync, utimesSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { isSystemNotification, ownedBy } from '../hooks/lib.mjs'

const HOOK = join(import.meta.dirname, '..', 'hooks', 'arm-nudge.mjs')
const SESSION = 'S'

function notification(summary) {
  return `<task-notification>\n<task-id>b1</task-id>\n<summary>${summary}</summary>\n</task-notification>`
}

const TICK_NOTIFICATION = notification('KEEPALIVE_TICK 1/6 ...')

function makeHome(t) {
  const home = mkdtempSync(join(tmpdir(), 'keepalive-test-'))
  t.after(() => rmSync(home, { recursive: true, force: true }))
  return home
}

function armLadder(t) {
  const home = makeHome(t)
  const dir = join(home, '.claude', 'keepalive', SESSION)
  mkdirSync(join(dir, 'rungs'), { recursive: true })
  writeFileSync(join(dir, 'owner'), SESSION, 'utf8')
  writeFileSync(join(dir, 'rungs', '2-6.alive'), '', 'utf8')
  return { home, dir }
}

const DEFAULT_GRACE = null

function hookEnv(home, graceMs) {
  const { KEEPALIVE_GRACE_MS, ...base } = process.env
  const env = { ...base, HOME: home, USERPROFILE: home }
  return graceMs === DEFAULT_GRACE ? env : { ...env, KEEPALIVE_GRACE_MS: graceMs }
}

function runHook(home, prompt, sessionId = SESSION, graceMs = '0') {
  return spawnSync(process.execPath, [HOOK], {
    input: JSON.stringify({ session_id: sessionId, prompt }),
    encoding: 'utf8',
    env: hookEnv(home, graceMs),
  })
}

test('a task notification is not the user coming back', t => {
  const { home, dir } = armLadder(t)
  const result = runHook(home, TICK_NOTIFICATION)
  assert.equal(result.status, 0)
  assert.equal(result.stdout, '')
  assert.equal(existsSync(join(dir, 'stop')), false)
})

test('a notification with leading whitespace is still a notification', t => {
  const { home, dir } = armLadder(t)
  const result = runHook(home, `\n  ${TICK_NOTIFICATION}`)
  assert.equal(result.status, 0)
  assert.equal(result.stdout, '')
  assert.equal(existsSync(join(dir, 'stop')), false)
})

test('a notification that quotes a leaving phrase does not arm a ladder', t => {
  const home = makeHome(t)
  const result = runHook(home, notification('workflow done: user afk, vuelvo en 2 horas'))
  assert.equal(result.status, 0)
  assert.equal(result.stdout, '')
  assert.equal(existsSync(join(home, '.claude', 'keepalive')), false)
})

test('a notification still reports a dead ladder', t => {
  const { home, dir } = armLadder(t)
  writeFileSync(join(dir, 'DEAD'), '1 peldanos sin latido', 'utf8')
  const result = runHook(home, TICK_NOTIFICATION)
  assert.equal(result.status, 0)
  assert.match(result.stdout, /murio/)
  assert.equal(existsSync(join(dir, 'stop')), false)
})

test('a real user message stops the ladder', t => {
  const { home, dir } = armLadder(t)
  const result = runHook(home, 'ya volví')
  assert.equal(result.status, 0)
  assert.equal(existsSync(join(dir, 'stop')), true)
})

test('isSystemNotification recognizes only prompts that open with a task notification', () => {
  assert.equal(isSystemNotification(TICK_NOTIFICATION), true)
  assert.equal(isSystemNotification(`\r\n\t ${TICK_NOTIFICATION}`), true)
  assert.equal(isSystemNotification('ya volví'), false)
  assert.equal(isSystemNotification(`mira esto: ${TICK_NOTIFICATION}`), false)
  assert.equal(isSystemNotification(''), false)
  assert.equal(isSystemNotification(undefined), false)
})

function armManualLadder(t) {
  const home = makeHome(t)
  const dir = join(home, '.claude', 'keepalive', 'sost')
  mkdirSync(join(dir, 'rungs'), { recursive: true })
  writeFileSync(join(dir, 'rungs', '2-6.alive'), '', 'utf8')
  return { home, dir }
}

test('a message from another session does not stop a ladder without owner', t => {
  const { home, dir } = armManualLadder(t)
  const result = runHook(home, 'revisa el build', 'OTHER')
  assert.equal(result.status, 0)
  assert.equal(existsSync(join(dir, 'stop')), false)
})

test('a ladder without owner does not block another session from arming its own', t => {
  const { home } = armManualLadder(t)
  const result = runHook(home, 'me voy a dormir', 'OTHER')
  assert.equal(result.status, 0)
  assert.match(result.stdout, /anuncia ausencia/)
  assert.doesNotMatch(result.stdout, /Ya hay una escalera viva/)
  assert.equal(existsSync(join(home, '.claude', 'keepalive', 'OTHER', 'owner')), true)
})

test('a message from another session does not stop an owned ladder', t => {
  const { home, dir } = armLadder(t)
  const result = runHook(home, 'ya volví', 'OTHER')
  assert.equal(result.status, 0)
  assert.equal(existsSync(join(dir, 'stop')), false)
})

test('the owner session is told its live ladder is already armed', t => {
  const { home } = armLadder(t)
  const result = runHook(home, 'me voy a dormir')
  assert.equal(result.status, 0)
  assert.match(result.stdout, /Ya hay una escalera viva/)
})

test('ownedBy requires both an owner and a session id that match', () => {
  assert.equal(ownedBy({ owner: 'A' }, 'A'), true)
  assert.equal(ownedBy({ owner: 'A' }, 'B'), false)
  assert.equal(ownedBy({ owner: null }, 'A'), false)
  assert.equal(ownedBy({ owner: 'A' }, null), false)
  assert.equal(ownedBy({ owner: null }, null), false)
})

const FIVE_HOURS_AGO = new Date(Date.now() - 5 * 60 * 60 * 1000)

function killedLadder(t, count = 3) {
  const home = makeHome(t)
  const dir = join(home, '.claude', 'keepalive', SESSION)
  mkdirSync(join(dir, 'rungs'), { recursive: true })
  writeFileSync(join(dir, 'owner'), SESSION, 'utf8')
  for (let rung = 1; rung <= count; rung++) {
    const alive = join(dir, 'rungs', `${rung}-${count}.alive`)
    writeFileSync(alive, '', 'utf8')
    utimesSync(alive, FIVE_HOURS_AGO, FIVE_HOURS_AGO)
  }
  return { home, dir }
}

function aliveNames(dir) {
  return readdirSync(join(dir, 'rungs')).filter(name => name.endsWith('.alive'))
}

test('coming back to a ladder whose rungs were all killed reports that it died', t => {
  const { home, dir } = killedLadder(t)
  const result = runHook(home, 'ya volví, sigamos', SESSION, DEFAULT_GRACE)
  assert.equal(result.status, 0)
  assert.match(result.stdout, /murio/)
  assert.match(result.stdout, /cache_audit/)
  assert.doesNotMatch(result.stdout, /0 peldanos restantes/)
  assert.equal(existsSync(join(dir, 'stop')), true)
})

test('a ladder with a DEAD marker is reported dead only once', t => {
  const { home, dir } = killedLadder(t)
  writeFileSync(join(dir, 'DEAD'), '3 peldanos sin latido', 'utf8')
  const result = runHook(home, 'ya volví')
  assert.equal(result.status, 0)
  assert.equal(result.stdout.match(/murio/g)?.length, 1)
  assert.doesNotMatch(result.stdout, /peldanos restantes/)
})

test('re-arming over a killed ladder clears its stale rungs', t => {
  const { home, dir } = killedLadder(t, 1)
  const result = runHook(home, 'me voy a dormir')
  assert.equal(result.status, 0)
  assert.match(result.stdout, /anuncia ausencia/)
  assert.deepEqual(aliveNames(dir), [])
})

test('a freshly re-armed ladder keeps its grace on the next message', t => {
  const { home, dir } = killedLadder(t, 1)
  runHook(home, 'me voy a dormir')
  writeFileSync(join(dir, 'rungs', '1-12.alive'), '', 'utf8')
  const result = runHook(home, '8 horas', SESSION, DEFAULT_GRACE)
  assert.equal(result.status, 0)
  assert.equal(existsSync(join(dir, 'stop')), false)
})
