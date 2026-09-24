import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { STALE_MS, aliveFiles, summarizeRungs } from '../hooks/lib.mjs'

const NOW = 1_000_000_000
const FIVE_HOURS = 5 * 60 * 60 * 1000

function rung(name, mtimeMs, bornMs = mtimeMs) {
  return { name, path: name, mtimeMs, bornMs }
}

function makeRungsDir(t, names) {
  const dir = mkdtempSync(join(tmpdir(), 'keepalive-test-'))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  for (const name of names) writeFileSync(join(dir, name), '', 'utf8')
  return dir
}

function missingFile(path) {
  return Object.assign(new Error(`ENOENT: no such file or directory, stat '${path}'`), { code: 'ENOENT' })
}

test('a ladder with only stale rungs is dead', () => {
  const summary = summarizeRungs([rung('a', NOW - FIVE_HOURS), rung('b', NOW - STALE_MS - 1)], NOW)
  assert.equal(summary.dead, true)
  assert.equal(summary.live.length, 0)
  assert.equal(summary.lastBeatMs, NOW - STALE_MS - 1)
})

test('a ladder with one live rung is not dead', () => {
  const summary = summarizeRungs([rung('a', NOW - FIVE_HOURS), rung('b', NOW)], NOW)
  assert.equal(summary.dead, false)
  assert.equal(summary.live.length, 1)
})

test('the arming time counts only live rungs', () => {
  const stale = rung('old', NOW - FIVE_HOURS, NOW - FIVE_HOURS)
  const live = rung('new', NOW, NOW - 1000)
  assert.equal(summarizeRungs([stale, live], NOW).armedAtMs, NOW - 1000)
  assert.equal(summarizeRungs([stale], NOW).armedAtMs, null)
})

test('aliveFiles skips a rung that deleted its .alive between readdir and stat', t => {
  const dir = makeRungsDir(t, ['1-2.alive', '2-2.alive', 'notes.txt'])
  const gone = join(dir, '1-2.alive')
  const stat = path => {
    if (path === gone) throw missingFile(path)
    return statSync(path)
  }
  assert.deepEqual(aliveFiles(dir, stat).map(file => file.name), ['2-2.alive'])
})

test('aliveFiles does not hide other stat errors', t => {
  const dir = makeRungsDir(t, ['1-1.alive'])
  const stat = () => { throw Object.assign(new Error('EPERM'), { code: 'EPERM' }) }
  assert.throws(() => aliveFiles(dir, stat), /EPERM/)
})
