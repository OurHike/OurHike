/**
 * The assist panel's failure mapping, which is the part that can be wrong
 * quietly.
 *
 * A 503 and a 502 differ by one digit and by whether the reader can do
 * anything about it. Getting that mapping wrong shows an organization a shrug
 * where there was an answer - "the assistant is off here" is a fact they can
 * act on, and "it did not answer" is not.
 */

import { describe, expect, it } from 'vitest'
import { standingFor } from './AssistPanel'

describe('standingFor', () => {
  it('reads a 503 as "the deployment has not switched this on"', () => {
    expect(standingFor(503)).toBe('off')
  })

  it('reads a 429 as "today\'s budget is spent", which has an answer', () => {
    expect(standingFor(429)).toBe('spent')
  })

  it('reads a 409 as "this organization has not opted in", not as an outage', () => {
    // The deployment has the assistant; the organization has not said yes to
    // it. Reading this as 'off' would tell an admin to talk to us, when the
    // switch is on their own Settings screen.
    expect(standingFor(409)).toBe('needsconsent')
  })

  it('reads a 502 as a shrug, because that is what it is', () => {
    expect(standingFor(502)).toBe('failed')
  })

  it('reads a 401 as a shrug rather than as a budget message', () => {
    // A signed-out caller must not be told they are out of budget.
    expect(standingFor(401)).toBe('failed')
  })

  it('reads a 422 the same way - a refused question is not an outage', () => {
    expect(standingFor(422)).toBe('failed')
  })

  it('treats a 200 as an answer', () => {
    expect(standingFor(200)).toBe('answered')
  })

  it('treats a thrown fetch, which has no status, as a shrug', () => {
    expect(standingFor(0)).toBe('failed')
  })
})
