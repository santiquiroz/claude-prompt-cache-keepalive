#!/usr/bin/env node
// Stop: flags a ladder whose rungs stopped heart-beating (VS Code reload, update, OS sleep).
import { writeFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { readStdin, parsePayload, listLadders, ownedBy, emit } from './lib.mjs'

const sessionId = parsePayload(await readStdin()).session_id ?? null
const broken = listLadders()
  .filter(ladder => ownedBy(ladder, sessionId))
  .filter(ladder => !ladder.stopped && ladder.stale.length > 0 && ladder.live.length === 0)

if (!broken.length) process.exit(0)

const lines = broken.map(ladder => {
  const marker = join(ladder.dir, 'DEAD')
  const last = new Date(Math.max(...ladder.stale.map(rung => rung.mtimeMs))).toISOString()
  if (!existsSync(marker)) writeFileSync(marker, `${ladder.stale.length} peldanos sin latido desde ${last}`, 'utf8')
  return `${ladder.dir}: ${ladder.stale.length} peldanos sin latido desde ${last}`
})

emit({ systemMessage: `[keepalive] escalera caida — re-armala si sigues fuera. ${lines.join(' | ')}` })
