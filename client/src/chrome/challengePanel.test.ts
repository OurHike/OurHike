import { describe, it, expect, afterEach, vi } from 'vitest'
import { cleanup, renderHook } from '@testing-library/react'
import type { Challenge } from '../lib/challenges'
import {
  EMPTY_CHALLENGE_STATE,
  join,
  type ChallengeState,
} from '../lib/challengeProgress'
import { useChallengePanel } from './challengePanel'

// The challenge layer's four props (#1780, features/CHALLENGES.md frame #1).
// What is tested here is the contract with the legend and the canvas: the
// row is offered only while a joined challenge is on the chosen trail, the
// switch starts off, and nothing is drawn that the row is not there to
// explain. Which places are pinned is map/challengePins.test.ts's.

afterEach(cleanup)

const NOW = new Date('2027-06-01T18:00:00Z')
const TODAY = '2027-06-01'

function challenge(id: string, trail: string): Challenge {
  return {
    id,
    org: 'atc',
    orgName: 'Appalachian Trail Conservancy',
    orgShort: 'ATC',
    trail,
    name: id,
    status: 'draft',
    summary: null,
    window: { opens: null, closes: null },
    finish: null,
    reward: null,
    photo: null,
    sections: [{ id: 's', title: 'Section', short: 'S' }],
    items: [
      {
        id: 'summit',
        section: 's',
        title: 'Stand on the summit',
        sealedTitle: null,
        note: null,
        noteBy: null,
        photo: null,
        match: {
          kind: 'place',
          radiusM: 150,
          offTrail: false,
          places: [
            {
              poi: `${id}:summit`,
              name: 'Summit',
              poiType: 'viewpoint',
              mile: 10,
              lat: 41,
              lon: -74,
            },
          ],
        },
        mystery: null,
      },
    ],
    reviewed: '2026-09-30',
  }
}

const AT_LIST = challenge('at-list', 'AT')
const LP_LIST = challenge('lp-list', 'LP')

function state(layerShown: boolean, ...joined: string[]): ChallengeState {
  const base = joined.reduce((s, id) => join(s, id, NOW), EMPTY_CHALLENGE_STATE)
  return { ...base, layerShown }
}

function panel(
  joined: readonly Challenge[],
  record: ChallengeState,
  chosenTrail: string | null,
) {
  const onToggle = vi.fn()
  const { result } = renderHook(() =>
    useChallengePanel({ joined, state: record, today: TODAY, chosenTrail, onToggle }),
  )
  return { props: result.current.mapScreen, onToggle }
}

describe('useChallengePanel', () => {
  it('offers no row, and draws nothing, for a hiker who joined nothing', () => {
    const { props } = panel([], state(true), 'AT')

    expect(props.onToggleChallengePlaces).toBeUndefined()
    expect(props.showChallengePins).toBe(false)
    expect(props.challengePins?.features).toEqual([])
  })

  it('offers no row when no joined challenge is on the chosen trail, and hides the layer', () => {
    // A switch that is not on screen must not be the reason something is
    // drawn - so a hiker who left it on and then took another trail sees
    // no diamonds and no row.
    const { props } = panel([LP_LIST], state(true, 'lp-list'), 'AT')

    expect(props.onToggleChallengePlaces).toBeUndefined()
    expect(props.showChallengePins).toBe(false)
    // The switch's own state is still the hiker's, for when the row returns.
    expect(props.challengePlacesShown).toBe(true)
  })

  it('offers no row with no trail taken at all', () => {
    expect(
      panel([AT_LIST], state(true, 'at-list'), null).props.onToggleChallengePlaces,
    ).toBeUndefined()
  })

  it('offers the row, off, when a joined challenge is on the chosen trail', () => {
    const { props, onToggle } = panel([AT_LIST], state(false, 'at-list'), 'AT')

    expect(props.onToggleChallengePlaces).toBe(onToggle)
    expect(props.challengePlacesShown).toBe(false)
    // Off by default draws nothing, though the pins are ready for the tap.
    expect(props.showChallengePins).toBe(false)
    expect(props.challengePins?.features).toHaveLength(1)
  })

  it('draws the pins once the hiker switches the layer on', () => {
    const { props } = panel([AT_LIST], state(true, 'at-list'), 'AT')

    expect(props.showChallengePins).toBe(true)
    expect(props.challengePlacesShown).toBe(true)
  })

  it('pins every joined challenge’s places, not only the chosen trail’s', () => {
    // A place is where it is; the chosen trail decides whether the layer is
    // offered, not which of the hiker's places exist.
    const { props } = panel([AT_LIST, LP_LIST], state(true, 'at-list', 'lp-list'), 'AT')

    expect(props.challengePins?.features.map((f) => f.properties.poi).sort()).toEqual([
      'at-list:summit',
      'lp-list:summit',
    ])
  })
})
