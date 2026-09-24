import { test } from 'node:test'
import assert from 'node:assert/strict'
import { detectLeaving } from '../hooks/lib.mjs'

const LEAVING = [
  'me voy a dormir',
  'vuelvo en 2 horas',
  'afk',
  'back in 2h',
  'going to bed',
  'me voy a almorzar, deja esto corriendo',
  'buenas noches, me voy a dormir',
  'listo por hoy, buenas noches',
  'hasta mañana!',
  'me voy, vuelvo en la tarde',
  'voy a estar afk',
  'vuelvo en 30 minutos',
  'vuelvo en 1h',
  'vuelvo en 45 min',
  'me voy, vuelvo en 20 min',
  'vuelvo en 1h, deja eso',
  'afk 2h',
  'brb 10 min',
]

const WORKING = [
  'buenas noches, revisa el PR 5334 por favor',
  'el log dice: user afk timeout',
  'cuando vuelvo en la tarde reviso',
  'me voy al grano: falla el build',
  'hasta mañana no necesito esto, arregla el test ya',
  'mira este log:\n```\n12:01 user afk timeout\n12:02 me voy a dormir\n```\nque significa?',
  'afk 2h de reuniones ayer, revisa el log',
  'el usuario escribio esto:\n> me voy a dormir, vuelvo en 2 horas\nporque no armo?',
]

for (const prompt of LEAVING) {
  test(`announces an absence: ${JSON.stringify(prompt)}`, () => {
    assert.equal(detectLeaving(prompt), true)
  })
}

for (const prompt of WORKING) {
  test(`is a work message: ${JSON.stringify(prompt)}`, () => {
    assert.equal(detectLeaving(prompt), false)
  })
}

const LONG_CONTEXT = 'Revisa el modulo de pagos, en especial la parte donde el usuario dice afk o me voy a dormir en el chat, porque el filtro de mensajes los marca mal. '.repeat(3)

test('a long message only counts its last sentence', () => {
  assert.equal(detectLeaving(`${LONG_CONTEXT}Arregla eso por favor.`), false)
  assert.equal(detectLeaving(`${LONG_CONTEXT}Yo me voy a dormir.`), true)
})

test('an unterminated code fence hides the rest of the message', () => {
  assert.equal(detectLeaving('revisa esto\n```\nafk'), false)
})

test('a missing prompt is not an absence', () => {
  assert.equal(detectLeaving(undefined), false)
})
