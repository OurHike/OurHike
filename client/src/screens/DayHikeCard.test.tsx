// Tests for screens/DayHikeCard.tsx - the finished day hike (#980).
//
// Two kinds of pin. The positive ones check the sourced blocks render from
// the LIVE resolution, org names from the steward join and never raw source
// keys. The negative ones are the point of the card's scope: nothing here may
// print a figure whose source does not exist yet - no ±ft, no parking, no
// "Chip in" - because a block invented to fill the frame is the exact failure
// CLAUDE.md's evidence standard names.
//
// ≈time and ± elevation moved sides with #1011: the graph carries per-edge
// climb now, so the card prints both when the walk can be priced and neither
// when it cannot. The tests below pin both halves - the numbers when there
// are numbers, and silence rather than a placeholder when there are not.

import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DayHikeCard } from './DayHikeCard'
import { STANDARD_PACE, type PaceProfile } from '../lib/pace'
import type { BailOut, ResolvedDayHike } from '../lib/dayHikeCard'
import type { DayHike } from '../lib/dayHikes'

afterEach(cleanup)

const HIKE: DayHike = {
  id: 'hike-1',
  name: 'Pine Meadow day hike',
  date: '2026-08-29',
  segments: [
    [
      { coord: [-74.095, 41.25], poiId: null },
      { coord: [-74.085, 41.25], poiId: null },
    ],
  ],
  // The stale cache: 5 miles, one leg. A card leaning on the live resolution
  // must never print these numbers.
  figures: {
    miles: 5,
    legs: [
      {
        name: 'Pine Meadow Trail',
        source: 'oprhp_trails',
        blaze_color: 'blue',
        miles: 5,
      },
    ],
  },
  looped: true,
  recorded: 'planned',
}

const RESOLVED: ResolvedDayHike = {
  segments: [],
  miles: 6.4,
  looped: true,
  // 1,240 ft of ascent over 6.4 miles - a plausible Harriman day, and enough
  // that Naismith's climb term is visible in the printed time rather than
  // rounding away.
  climb: { gainFt: 1240, lossFt: 1180 },
  legs: [
    {
      name: 'Pine Meadow Trail',
      source: 'oprhp_trails',
      blaze_color: 'blue',
      trail_id: 'oprhp_trails:1',
      miles: 2.1,
    },
    {
      name: 'Seven Hills Trail',
      source: 'nynjtc_long_path',
      blaze_color: 'white',
      trail_id: 'nynjtc_long_path:2',
      miles: 4.3,
    },
  ],
}

const BAIL_OUTS: BailOut[] = [
  { miles: 3.2, name: 'Kakiat Trail', blaze_color: 'white', source: 'nynjtc_long_path' },
]

function renderCard(overrides: Partial<Parameters<typeof DayHikeCard>[0]> = {}) {
  return render(
    <DayHikeCard
      hike={HIKE}
      resolved={RESOLVED}
      bailOuts={BAIL_OUTS}
      units="imperial"
      pace={STANDARD_PACE}
      networkAvailable={true}
      mode="saved"
      onClose={vi.fn()}
      onDelete={vi.fn()}
      {...overrides}
    />,
  )
}

describe('the sourced blocks', () => {
  it('prints the live figures, the legs with their orgs, and the LOOP badge', () => {
    renderCard()

    expect(screen.getByText(/6\.4 mi · 2 legs/)).toBeInTheDocument()
    expect(screen.getByText('LOOP')).toBeInTheDocument()
    expect(screen.getByText('sat 29 aug')).toBeInTheDocument()
    expect(screen.getByText('Seven Hills Trail')).toBeInTheDocument()
    // Per-leg miles, back since #1002 priced them at the walked metres.
    expect(screen.getByText('2.1 mi')).toBeInTheDocument()
    expect(screen.getByText('4.3 mi')).toBeInTheDocument()
    // The maintaining organization is NOT on the row any more (#1112): it
    // repeated per leg, it is the least actionable part of a row read to walk
    // by, and the published names are long enough to break the layout. Both
    // spellings are asserted absent, because the bug was the resolved NAME
    // and the fallback is the raw KEY - dropping one and leaving the other
    // would look fixed on a phone with no stewards export and nowhere else.
    expect(screen.queryByText(/NYS Parks/)).not.toBeInTheDocument()
    expect(screen.queryByText(/oprhp_trails/)).not.toBeInTheDocument()
    // The credit survives as a COUNT, which is what it always was - orgCount
    // reads leg.source, so it never depended on the labels that left.
    expect(
      screen.getByText(/Two organizations keep this loop walkable/),
    ).toBeInTheDocument()
  })

  it('prints a way off with its mile, name and blaze', () => {
    renderCard()

    expect(screen.getByText('If you need to get off')).toBeInTheDocument()
    // A walked length, so it converts for a metric hiker - not the A.T.'s
    // "mi 3.2" marker voice, which names a point that never converts.
    expect(screen.getByText('at 3.2 mi')).toBeInTheDocument()
    expect(screen.getByText(/Kakiat Trail \(white\)/)).toBeInTheDocument()
    // The blaze stays and the organization goes, which is the split #1112
    // settled: a hiker leaving a route in a hurry navigates by the blaze, and
    // whose ground it is does not help them get down.
    expect(screen.queryByText(/NY–NJ Trail Conference/)).not.toBeInTheDocument()
    expect(screen.queryByText(/nynjtc_long_path/)).not.toBeInTheDocument()
  })

  it('says so when no marked trail leaves the route, rather than omitting the block', () => {
    renderCard({ bailOuts: [] })

    expect(screen.getByText(/No marked trail leaves this loop/)).toBeInTheDocument()
  })
})

describe('the honest absences', () => {
  it('prices nothing when the walk crosses ground nobody measured', () => {
    // climb: null is not "flat" - it is a phone with no elevation artifact, or
    // a walk crossing an edge in a DEM gap. Either way a ≈ here would be an
    // invented figure wearing an honest prefix.
    renderCard({ resolved: { ...RESOLVED, climb: null } })

    expect(screen.queryByText(/≈/)).not.toBeInTheDocument()
    expect(screen.queryByText(/walking\b/)).not.toBeInTheDocument()
    expect(screen.queryByText(/ft\b/)).not.toBeInTheDocument()
    // And no estimate note either, which would otherwise be a caveat about a
    // number that is not on the screen.
    expect(
      screen.queryByText(/estimates from the best elevation data/),
    ).not.toBeInTheDocument()
  })

  it('promises nothing it still has no source for', () => {
    renderCard()

    // Parking waits on #981's pipeline data and the donate link on wording no
    // steward has given us. Climb no longer waits on anything (#1011).
    expect(screen.queryByText(/Parking/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Chip in/)).not.toBeInTheDocument()
  })

  it('falls back to the stored cache with the no-network sentence', () => {
    renderCard({ resolved: null, networkAvailable: false })

    // The cache's own numbers, under a sentence saying that is what they are.
    expect(screen.getByText(/5\.0 mi · 1 leg\b/)).toBeInTheDocument()
    // "no trail network", not "not yet" - #1049. There is no graph coming
    // on production (#1048), and "yet" was the same false promise the plan
    // door was making.
    expect(screen.getByText(/has no trail network/)).toBeInTheDocument()
    expect(screen.queryByText(/network yet/)).not.toBeInTheDocument()
    // No ways-off section at all: nothing honest to put in it.
    expect(screen.queryByText('If you need to get off')).not.toBeInTheDocument()
  })

  it('says when the current map cannot place the walk, which is a different sentence', () => {
    renderCard({ resolved: null, networkAvailable: true })

    expect(
      screen.getByText(/current trail map can.t place this walk/),
    ).toBeInTheDocument()
  })

  it('credits no organization on a walk whose legs nobody attributed', () => {
    renderCard({
      resolved: {
        ...RESOLVED,
        legs: [
          {
            name: 'Old Woods Road',
            source: null,
            blaze_color: null,
            trail_id: null,
            miles: 6.4,
          },
        ],
      },
    })

    expect(screen.queryByText(/organizations? keeps?/)).not.toBeInTheDocument()
  })
})

describe('the two modes', () => {
  it('review offers Save as the one primary, and no delete', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    renderCard({ mode: 'review', onSave })

    await user.click(screen.getByRole('button', { name: 'Save this day hike' }))
    expect(onSave).toHaveBeenCalledOnce()
    expect(screen.queryByText(/Delete/)).not.toBeInTheDocument()
  })

  it('saved deletes in two taps, and Keep it disarms', async () => {
    const user = userEvent.setup()
    const onDelete = vi.fn()
    renderCard({ onDelete })

    await user.click(screen.getByRole('button', { name: 'Delete this day hike' }))
    expect(onDelete).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Keep it' }))
    expect(screen.queryByText('Delete this day hike?')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Delete this day hike' }))
    await user.click(screen.getByRole('button', { name: 'Delete' }))
    expect(onDelete).toHaveBeenCalledOnce()
  })
})

describe('the door onto the ground (#1041)', () => {
  const FOLLOW = { name: 'Follow this hike on the map' }

  it('offers following once the walk is saved and the graph can place it', async () => {
    const user = userEvent.setup()
    const onFollow = vi.fn()
    renderCard({ onFollow })

    await user.click(screen.getByRole('button', FOLLOW))
    expect(onFollow).toHaveBeenCalledOnce()
  })

  it('does not offer it over the stored cache', () => {
    // Following is a live position against a ROUTE, and with `resolved` null
    // the card is leaning on a list of figures rather than on ground. Absent
    // rather than disabled: a greyed control is a promise the app cannot say
    // why it is not keeping.
    renderCard({ onFollow: vi.fn(), resolved: null })

    expect(screen.queryByRole('button', FOLLOW)).not.toBeInTheDocument()
  })

  it('does not offer it on a review, which has no record to point at', () => {
    renderCard({ mode: 'review', onSave: vi.fn() })

    expect(screen.queryByRole('button', FOLLOW)).not.toBeInTheDocument()
  })
})

describe('the #1008 additions', () => {
  it('offers the date as a field the hiker sets, and clearing it clears the date', async () => {
    const user = userEvent.setup()
    const onSetDate = vi.fn()
    renderCard({ onSetDate })

    const field = screen.getByLabelText('When') as HTMLInputElement
    expect(field.value).toBe('2026-08-29')

    await user.clear(field)
    expect(onSetDate).toHaveBeenLastCalledWith(null)
  })

  it('shows no date field at all when the shell offers no way to keep one', () => {
    renderCard()
    expect(screen.queryByLabelText('When')).not.toBeInTheDocument()
  })

  it('draws a gap as a gap: straight-line miles and the refusal to route it', () => {
    renderCard({
      hike: {
        ...HIKE,
        looped: false,
        segments: [
          [
            { coord: [-74.095, 41.25], poiId: null },
            { coord: [-74.09, 41.25], poiId: null },
          ],
          [
            { coord: [-74.085, 41.25], poiId: null },
            { coord: [-74.08, 41.25], poiId: null },
          ],
        ],
      },
      // The cache path: a multi-segment loop refuses resolution anyway.
      resolved: null,
    })

    expect(
      screen.getByText(/with no trail under it, straight across/),
    ).toBeInTheDocument()
    expect(screen.getByText(/that stretch is yours/)).toBeInTheDocument()
  })

  it('a single-segment walk shows no gap row - nothing to be honest about', () => {
    renderCard()
    expect(screen.queryByText(/no trail under it/)).not.toBeInTheDocument()
  })

  it('saved mode opens Leave this with someone in the same sheet frame', async () => {
    const user = userEvent.setup()
    renderCard()

    await user.click(screen.getByRole('button', { name: 'Leave this with someone' }))
    expect(
      screen.getByRole('dialog', { name: 'Leave this with someone' }),
    ).toBeInTheDocument()
    // The card's own blocks stepped aside; the close returns to them.
    expect(screen.queryByText('Legs')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Close' }))
    expect(screen.getByText('Legs')).toBeInTheDocument()
  })

  it('review mode offers no leave door - Save stays the one primary', () => {
    renderCard({ mode: 'review', onSave: vi.fn() })
    expect(
      screen.queryByRole('button', { name: 'Leave this with someone' }),
    ).not.toBeInTheDocument()
  })
})

describe('the climb, once the phone can price it (#1011)', () => {
  it('prints ascent and descent beside the miles', () => {
    renderCard()

    expect(screen.getByText(/\+1,240 ft/)).toBeInTheDocument()
    expect(screen.getByText(/−1,180 ft/)).toBeInTheDocument()
  })

  it('prints a walking time with the ≈ prefix and the qualifier', () => {
    // WIREFRAMES.md's load-bearing rules, unchanged by this being a network
    // hike: ≈ always, "walking" always, and never an arrival clock.
    renderCard()

    expect(screen.getByText(/≈.*walking/)).toBeInTheDocument()
    expect(screen.queryByText(/arrive|arrival|by \d/i)).not.toBeInTheDocument()
  })

  it('prices the climb into the time rather than timing the miles alone', () => {
    // Pinned exactly, because the whole point of #1011 is that the climb term
    // is no longer zero. 6.4 mi at 5 km/h is 123.6 min; 1,240 ft of ascent
    // adds 37.8 more at Naismith's 1h/600m; 161.4 rounds to 160 = 2h 40m.
    // Distance alone would print ≈2h 5m, so this test fails if the ascent
    // term ever silently drops back out.
    renderCard()

    expect(screen.getByText(/≈2h 40m walking/)).toBeInTheDocument()
  })

  it("walks this day at the hiker's own pace, and says so (#1040)", () => {
    // The half this card did not have. It priced with naismithMinutes - the
    // STANDARD rule - so a hiker who told this app they walk at 2 mph read
    // their A.T. plan at 2 and their day hike at 3.107, with nothing on
    // either screen saying which was which.
    const slow: PaceProfile = { ...STANDARD_PACE, flatPaceMph: 2 }
    renderCard({ pace: slow })

    // 6.4 mi at 2 mph is 192 min; 1,240 ft of ascent adds 37.8 at Naismith's
    // own climb term, which this control does not move; 229.8 -> ≈3h 50m.
    expect(screen.getByText(/≈3h 50m walking/)).toBeInTheDocument()
    // And what it was adjusted from, so the figure cannot pass as the rule's
    // own (#851).
    expect(screen.getByText('was ≈2h 40m · 1.4× standard')).toBeInTheDocument()
  })

  it('adds the descent penalty this walk measured, when one is set (#900)', () => {
    // routeClimb measured 1,180 ft of loss and the card used to throw it
    // away. A hiker who set the knee penalty is asking for exactly this walk
    // to cost more; the control only ever ADDS time, so the direction is the
    // cautious one.
    const knees: PaceProfile = { ...STANDARD_PACE, descentMinutesPer1000m: 60 }
    renderCard({ pace: knees })

    // 161.4 standard minutes plus 1,180 ft = 359.7 m of descent at an hour
    // per 1,000 m: 21.6 more, 183 -> ≈3h 5m.
    expect(screen.getByText(/≈3h 5m walking/)).toBeInTheDocument()
  })

  it('says nothing about pace when the hiker never moved a control', () => {
    // The other half of #851's rule: "1.0× standard" on a fresh install is a
    // caveat that teaches hikers to stop reading the ones that matter.
    renderCard()

    expect(screen.queryByText(/standard/)).not.toBeInTheDocument()
  })

  it('says the figures are estimates rather than letting them read as surveyed', () => {
    // The maintainer's call, 2026-08-25. The pipeline's own gate reads +18.8%
    // against a maintaining club on terrain like this, so a hiker comparing
    // against a guidebook needs to know which kind of number this is.
    renderCard()

    expect(
      screen.getByText(/estimates from the best elevation data available/),
    ).toBeInTheDocument()
  })

  it('says the time is moving time, which is what stops it reading as a promise', () => {
    // #1042. The storyboard names this sentence as one of the two reasons
    // frame D5 exists, and #1008 shipped the ≈time without it. It is a
    // DIFFERENT claim from the estimates note beside it: that one is about how
    // precise the figure is, this one about what it measures at all. A hiker
    // can believe the first and still be an hour late because of the second.
    renderCard()

    expect(
      screen.getByText(/knows nothing about lunch, a swim, or half an hour/),
    ).toBeInTheDocument()
  })

  it('warns about both things at once, or a reader skips the pair', () => {
    // Two `role="note"` paragraphs in a row read as boilerplate. One note, and
    // the sentence that matters is not the one that gets skipped.
    renderCard()

    const notes = screen
      .getAllByRole('note')
      .filter((node) =>
        /Moving time|estimates from the best/.test(node.textContent ?? ''),
      )
    expect(notes).toHaveLength(1)
    expect(notes[0].textContent).toMatch(/Moving time/)
    expect(notes[0].textContent).toMatch(/estimates from the best elevation data/)
  })

  it('says neither thing when there is no time to qualify', () => {
    // A caveat about a number that is not on the screen is noise, and the
    // absence is the honest output - not a degraded one.
    renderCard({ resolved: { ...RESOLVED, climb: null } })

    expect(screen.queryByText(/knows nothing about lunch/)).not.toBeInTheDocument()
    expect(
      screen.queryByText(/estimates from the best elevation data/),
    ).not.toBeInTheDocument()
  })

  it('never prints a climb over the stored cache, which has none', () => {
    // The cache was written before any of this existed. Printing today's
    // climb over yesterday's walk would be a display outrunning its source -
    // the same rule the miles fallback already states in a sentence.
    renderCard({ resolved: null, networkAvailable: false })

    expect(screen.queryByText(/ft\b/)).not.toBeInTheDocument()
    expect(screen.queryByText(/≈/)).not.toBeInTheDocument()
  })
})
