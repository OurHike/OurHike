import { describe, expect, it } from 'vitest'

import { accountTag } from './accountTag'

// The tag a queued usage row carries so it is only ever sent with its own
// account's token (lib/usageQueue.ts). What it has to be is stable for one
// account and different for two - nothing more is asked of it.

describe('accountTag', () => {
  it('gives one account the same tag however its email is typed', () => {
    expect(accountTag('Hiker@Example.org ')).toBe(accountTag('hiker@example.org'))
  })

  it('tells two accounts on one phone apart', () => {
    expect(accountTag('alice@example.org')).not.toBe(accountTag('bob@example.org'))
  })

  it('does not carry the email in it', () => {
    expect(accountTag('alice@example.org')).not.toContain('alice')
  })
})
