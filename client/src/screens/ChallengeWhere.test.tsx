// "Where your trail karma is" (#1965). The map hook is mocked so a case can
// hold the phone with a map and without one; the drawing itself is
// lib/challengeMapSvg.test.ts's.

import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ATC_CHALLENGE } from '../lib/challenges.fixtures'
import { fixtureMap } from '../lib/challengeMap.fixtures'
import { EMPTY_CHALLENGE_STATE, join, tag, tagsFor } from '../lib/challengeProgress'
import type { ChallengeMap } from '../lib/challengeMap'
import type { TagPlace } from '../lib/tagPlace'
import { ChallengeWhere } from './ChallengeWhere'

const held = vi.hoisted(() => ({ map: null as ChallengeMap | null }))

vi.mock('../lib/useChallengeMap', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/useChallengeMap')>()),
  useChallengeMap: () => held.map,
}))

afterEach(() => {
  cleanup()
  held.map = null
})

const item = (id: string) => ATC_CHALLENGE.items.find((entry) => entry.id === id)!

function earned(entries: { id: string; place?: TagPlace; how?: 'gps' | 'hand' }[]) {
  let state = join(
    EMPTY_CHALLENGE_STATE,
    ATC_CHALLENGE.id,
    new Date('2027-06-01T12:00:00Z'),
  )
  for (const entry of entries)
    state = tag(state, ATC_CHALLENGE, item(entry.id), {
      at: new Date('2027-07-02T15:00:00Z'),
      how: entry.how ?? 'hand',
      place: entry.place,
    }).state
  return tagsFor(state, ATC_CHALLENGE.id)
}

function where(tags = earned([])) {
  render(
    <ChallengeWhere
      challenge={ATC_CHALLENGE}
      tags={tags}
      today="2027-07-14"
      walked={[]}
      units="imperial"
    />,
  )
}

describe('where your trail karma is (#1965)', () => {
  it('lists earned items under the state each landed in, south to north, with where and when', () => {
    where(
      earned([
        { id: 'mcafee-knob', how: 'gps' },
        { id: 'springer-mountain' },
        { id: 'white-blaze-photo', place: { kind: 'state', state: 'WV' } },
      ]),
    )
    const headings = screen
      .getAllByRole('heading', { level: 2 })
      .map((heading) => heading.textContent)
    expect(headings.slice(0, 3)).toEqual(['Georgia', 'Virginia', 'West Virginia'])
    expect(
      screen.getByText(/McAfee Knob Summit · mi 714\.9 · from your walk/),
    ).toBeInTheDocument()
    expect(screen.getByText('On the trail in West Virginia')).toBeInTheDocument()
    expect(
      screen.getByText('3 earned on the trail, 0 at home. Where stays on this phone.'),
    ).toBeInTheDocument()
  })

  it('puts what happened off the trail under its own heading, and names the places still on the card without a count', () => {
    where(
      earned([{ id: 'trivia-quiz' }, { id: 'pick-up-litter', place: { kind: 'off' } }]),
    )
    const off = screen.getByRole('heading', { name: 'Not on the trail' }).parentElement!
    expect(within(off).getAllByRole('listitem')).toHaveLength(2)
    const still = screen.getByRole('heading', {
      name: 'Also on your card',
    }).parentElement!
    expect(within(still).getAllByRole('listitem').length).toBeGreaterThan(0)
    expect(still.textContent).not.toMatch(/\+\d|\d+ (more|left|to go)/)
  })

  it('puts what the walk earned with no state on the phone under "On the trail", never at home (review of #2020)', () => {
    where(
      earned([
        { id: 'shelter-logbook', how: 'gps' },
        { id: 'summit-4000', how: 'gps' },
      ]),
    )
    const trail = screen.getByRole('heading', { name: 'On the trail' }).parentElement!
    expect(within(trail).getAllByRole('listitem')).toHaveLength(2)
    expect(screen.queryByRole('heading', { name: 'Not on the trail' })).toBeNull()
    expect(
      screen.getByText('2 earned on the trail, 0 at home. Where stays on this phone.'),
    ).toBeInTheDocument()
  })

  it('says so plainly when nothing is earned, and draws no map until something is on the trail', () => {
    held.map = fixtureMap()
    where()
    expect(screen.getByText(/Nothing earned yet/)).toBeInTheDocument()
    expect(document.querySelector('.challenge-where__map')).toBeNull()
  })

  it('draws the map once an earned item is on the trail and the phone holds a map', () => {
    held.map = fixtureMap()
    where(earned([{ id: 'mcafee-knob' }]))
    expect(document.querySelector('.challenge-where__map svg')).not.toBeNull()
  })

  it('shows the list alone, with no word about a missing map, when the phone holds none', () => {
    where(earned([{ id: 'mcafee-knob' }]))
    expect(document.querySelector('.challenge-where__map')).toBeNull()
    expect(document.body.textContent).not.toMatch(/no map|map is missing|download/i)
  })
})
