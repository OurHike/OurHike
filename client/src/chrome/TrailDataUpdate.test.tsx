// The ask itself (#919) - what a hiker reads before their map is replaced.
//
// These are about the sentences. What decides whether the row appears at all
// is lib/dataRefresh.test.ts; what is asserted here is that the row never says
// more than it knows, which is where a prompt about safety data can do harm.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { TrailDataUpdate, describeChange, describeSize } from './TrailDataUpdate'
import { CONSEQUENTIAL, ROUTINE } from '../lib/dataManifest'
import type { AvailableRefresh } from '../lib/dataRefresh'

afterEach(() => {
  // This suite renders the same row several times per describe. Explicit
  // rather than relying on an auto-cleanup this project does not configure -
  // chrome/Legend.test.tsx does the same, for the same reason.
  cleanup()
})

const update = (overrides: Partial<AvailableRefresh> = {}): AvailableRefresh => ({
  version: 'v2',
  keys: ['poi_water.geojson'],
  severity: ROUTINE,
  described: true,
  added: 0,
  removed: 0,
  moved: 0,
  edited: 0,
  bytes: 500_000,
  ...overrides,
})

function show(overrides: Partial<AvailableRefresh> = {}, props = {}) {
  const onApply = vi.fn()
  const onDecline = vi.fn()
  render(
    <TrailDataUpdate
      update={update(overrides)}
      warnsAboutData={false}
      applying={false}
      onApply={onApply}
      onDecline={onDecline}
      {...props}
    />,
  )
  return { onApply, onDecline }
}

describe('whether it appears', () => {
  it('renders nothing when the map is current', () => {
    const { container } = render(
      <TrailDataUpdate
        update={null}
        warnsAboutData={false}
        applying={false}
        onApply={vi.fn()}
        onDecline={vi.fn()}
      />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('asks rather than announcing, for a routine release too', () => {
    // The maintainer's decision (2026-08-21): nothing is replaced without
    // being asked. Severity shapes what this says, never whether it appears.
    show({ severity: ROUTINE, added: 4 })
    expect(screen.getByRole('button', { name: 'Update' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Not now' })).toBeInTheDocument()
  })
})

describe('what it says changed', () => {
  it('leads with what was removed, because that is what a hiker loses', () => {
    expect(describeChange(update({ added: 9, removed: 2 }))).toBe(
      'Waypoints: 2 removed, 9 added.',
    )
  })

  it('names moved separately from removed', () => {
    expect(describeChange(update({ moved: 3 }))).toBe('Waypoints: 3 moved.')
  })

  it('admits it cannot say when the release does not describe this hop', () => {
    // A phone two releases behind. Listing counts from somebody else's
    // transition would be the plausible sentence rather than the true one.
    expect(describeChange(update({ described: false, added: 5 }))).toBe(
      'The map data has changed since this was downloaded.',
    )
  })

  it('still says something true when every count is zero', () => {
    expect(describeChange(update())).toBe('Waypoints and trail lines updated.')
  })
})

describe('what it says it costs', () => {
  it('shows the size plainly when there is nothing to caution about', () => {
    show({ bytes: 5_784_212 })
    expect(screen.getByText('About 5.8 MB.')).toBeInTheDocument()
  })

  it('warns about mobile data when told to', () => {
    show({ bytes: 5_784_212 }, { warnsAboutData: true })
    expect(
      screen.getByText('About 5.8 MB. This may use mobile data.'),
    ).toBeInTheDocument()
  })

  it('never renders an unknown size as free', () => {
    show({ bytes: null }, { warnsAboutData: true })
    expect(screen.getByText('Downloading this may use mobile data.')).toBeInTheDocument()
    expect(screen.queryByText(/0 MB/)).not.toBeInTheDocument()
  })

  it('omits the cost line entirely when there is no size and no caution', () => {
    show({ bytes: null })
    expect(screen.queryByText(/MB/)).not.toBeInTheDocument()
  })

  it('rounds for reading rather than for measurement', () => {
    expect(describeSize(5_784_212)).toBe('5.8 MB')
    expect(describeSize(48_000_000)).toBe('48 MB')
    expect(describeSize(50_000)).toBe('<0.1 MB')
    expect(describeSize(null)).toBeNull()
  })
})

describe('the two answers', () => {
  it('takes the update', async () => {
    const { onApply } = show()
    await userEvent.click(screen.getByRole('button', { name: 'Update' }))
    expect(onApply).toHaveBeenCalledTimes(1)
  })

  it('declines it', async () => {
    const { onDecline } = show()
    await userEvent.click(screen.getByRole('button', { name: 'Not now' }))
    expect(onDecline).toHaveBeenCalledTimes(1)
  })

  it('says the bytes are coming rather than vanishing into an unchanged map', async () => {
    show({}, { applying: true })
    expect(screen.getByRole('button', { name: 'Updating…' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Not now' })).toBeDisabled()
  })
})

describe('how loudly', () => {
  it('marks a release that removed or moved something', () => {
    const { container } = render(
      <TrailDataUpdate
        update={update({ severity: CONSEQUENTIAL, removed: 1 })}
        warnsAboutData={false}
        applying={false}
        onApply={vi.fn()}
        onDecline={vi.fn()}
      />,
    )
    expect(container.querySelector('.trail-data-update--serious')).not.toBeNull()
  })

  it('does not mark a routine one', () => {
    const { container } = render(
      <TrailDataUpdate
        update={update({ severity: ROUTINE, added: 1 })}
        warnsAboutData={false}
        applying={false}
        onApply={vi.fn()}
        onDecline={vi.fn()}
      />,
    )
    expect(container.querySelector('.trail-data-update--serious')).toBeNull()
  })
})
