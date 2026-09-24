import { test } from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { isSystemNotification } from '../hooks/lib.mjs'

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

function runHook(home, prompt) {
  return spawnSync(process.execPath, [HOOK], {
    input: JSON.stringify({ session_id: SESSION, prompt }),
    encoding: 'utf8',
    env: { ...process.env, HOME: home, USERPROFILE: home, KEEPALIVE_GRACE_MS: '0' },
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
