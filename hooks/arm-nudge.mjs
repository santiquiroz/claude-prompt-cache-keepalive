#!/usr/bin/env node
// UserPromptSubmit: arms the keepalive ladder when the user announces an absence,
// and stops it the moment they come back.
import { existsSync, writeFileSync, rmSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { readStdin, parsePayload, isSystemNotification, listLadders, ownedBy, createStateDir, emit } from './lib.mjs'

const SKILL_DIR = join(import.meta.dirname, '..')
const GRACE_MS = Number(process.env.KEEPALIVE_GRACE_MS ?? 10 * 60 * 1000)
const AUDIT_HINT = 'El cache pudo haberse enfriado; verificalo con scripts/cache_audit.py antes de afirmar nada.'

const AWAY = [
  /\bme voy a dormir\b/i, /\bvoy a dormir\b/i, /\bme duermo\b/i, /\bbuenas noches\b/i,
  /\bhasta ma(n|ñ)ana\b/i, /\bme ausento\b/i, /\bme desconecto\b/i, /\bme voy (un rato|para|a la|al )/i,
  /\bvuelvo (en|m(a|á)s tarde|luego|despu(e|é)s)\b/i, /\best(a|á)r(e|é) fuera\b/i, /\bno voy a estar\b/i,
  /\bvoy a (almorzar|comer|salir)\b/i, /\bsalgo a\b/i, /\bentro a una reuni(o|ó)n\b/i,
  /\bmientras (duermo|no est(o|é)y|estoy fuera)\b/i, /\bdeja(lo)? (esto )?corriendo\b/i,
  /\bafk\b/i, /\bbrb\b/i, /\bgoing to (bed|sleep)\b/i, /\bstepping away\b/i, /\bback in \d/i,
]

const raw = await readStdin()
const payload = parsePayload(raw)
const prompt = String(payload.prompt ?? '')
const sessionId = payload.session_id ?? null
const notification = isSystemNotification(prompt)
const leaving = !notification && AWAY.some(pattern => pattern.test(prompt))
const mine = listLadders()
  .filter(l => !l.stopped && ownedBy(l, sessionId))
  .map(ladder => ({ ...ladder, marked: existsSync(join(ladder.dir, 'DEAD')) }))
const notes = []

function isPastGrace(ladder) {
  return ladder.dead || Date.now() - ladder.armedAtMs >= GRACE_MS
}

function deadNote(ladder) {
  const since = new Date(ladder.lastBeatMs).toISOString()
  return `La escalera de ${ladder.dir} murio desde ${since}: sus ${ladder.stale.length} peldanos dejaron de latir (reload de la ventana, actualizacion o suspension) y la detuve. ${AUDIT_HINT}`
}

function returnNote(ladder) {
  if (!ladder.dead) return `El usuario volvio: escribi ${join(ladder.dir, 'stop')} y la escalera se detiene sola. Los ${ladder.live.length} peldanos restantes saldran con KEEPALIVE_STOPPED; responde cada uno con una linea y sin herramientas.`
  if (ladder.marked) return null
  return deadNote(ladder)
}

for (const ladder of mine.filter(l => l.marked)) {
  const deadMarker = join(ladder.dir, 'DEAD')
  notes.push(`La escalera de ${ladder.dir} murio: ${readFileSync(deadMarker, 'utf8').trim()}. ${AUDIT_HINT}`)
  rmSync(deadMarker, { force: true })
}

if (leaving) {
  const armed = mine.find(ladder => ladder.live.length > 0)
  if (armed) {
    notes.push(`Ya hay una escalera viva en ${armed.dir} con ${armed.live.length} peldanos. No la re-armes: confirma cuantos quedan y cuanto cubren.`)
  } else {
    const dir = createStateDir(sessionId)
    notes.push(
      `El usuario anuncia ausencia. ANTES de responder invoca la skill keeping-prompt-cache-warm y arma la escalera COMPLETA en este mismo turno:\n` +
      `1) Estima las horas de ausencia por lo que dijo el usuario (si no lo dice, pregunta en una linea y arma 8 h por defecto).\n` +
      `2) python ${join(SKILL_DIR, 'scripts', 'plan.py')} --hours H --every 40 --first F  (F por debajo de los minutos de cache restantes menos 10).\n` +
      `3) Lanza TODOS los peldanos en un solo mensaje, en paralelo, con run_in_background:\n` +
      `   & '${join(SKILL_DIR, 'scripts', 'rung.ps1')}' -Minutes M -Label 'k/N' -StateDir '${dir}'\n` +
      `4) State dir ya creado y sin archivo stop: ${dir}. No uses otro.\n` +
      `5) No des por terminada la respuesta hasta que cada peldano figure como tarea en background.`
    )
  }
} else if (!notification) {
  for (const ladder of mine.filter(isPastGrace)) {
    writeFileSync(join(ladder.dir, 'stop'), new Date().toISOString(), 'utf8')
    const note = returnNote(ladder)
    if (note) notes.push(note)
  }
}

if (!notes.length) process.exit(0)
emit({
  hookSpecificOutput: { hookEventName: 'UserPromptSubmit', additionalContext: `[keepalive] ${notes.join('\n')}` },
  systemMessage: `[keepalive] ${leaving ? 'armar escalera de cache' : 'escalera detenida / novedades'}`,
})
