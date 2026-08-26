// Tests for chrome/PlanKindSheet.tsx - the door into the builder (#977,
// wireframe frame `1i`).
//
// What is worth testing here is not the layout. It is the three commitments
// the sheet exists to keep:
//
//   1. It OPENS from PlanHome's one primary action rather than adding a second
//      call to action - so the sheet itself carries no competing primary.
//   2. The sentence separating a day hike from a trip is present, because two
//      options whose names both start with a duration read as one question
//      asked twice without it.
//   3. When there is no network to route on, the day-hike option is a
//      SENTENCE and not a control that looks pressable and is not
//      (chrome/LineSheet.tsx's rule).
//   4. That sentence is TRUE OF THE ABSENCE IT IS ABOUT (#1049). It used to be
//      one sentence for all five, ending "It arrives with the next data sync",
//      and four of the five never resolve by waiting - so on production, where
//      the graph is simply not in the release (#1048), every hiker who tapped
//      this door was told to wait for something that was never coming.

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { PlanKindSheet } from './PlanKindSheet'
import type { TrailNetworkState } from '../lib/trailGraphData'

const READY: TrailNetworkState = { kind: 'ready' }
const absent = (
  because:
    'unconfigured' | 'unreachable' | 'not-in-release' | 'unverifiable' | 'not-a-graph',
): TrailNetworkState => ({ kind: 'absent', because })

// This suite renders the same sheet many times; the repo's convention is an
// explicit cleanup rather than relying on a global one.
afterEach(() => {
  cleanup()
})

function renderSheet(overrides: Partial<Parameters<typeof PlanKindSheet>[0]> = {}) {
  const props = {
    network: READY,
    walkedAvailable: true,
    onPickDayHike: vi.fn(),
    onPickTrip: vi.fn(),
    onPickWalked: vi.fn(),
    onClose: vi.fn(),
    ...overrides,
  }
  render(<PlanKindSheet {...props} />)
  return props
}

describe('the three doors', () => {
  it('offers a day hike, a trip and a walk already done', () => {
    renderSheet()

    expect(screen.getByRole('button', { name: /A day hike/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /A multi-day trip/ })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /A walk I.{0,3}ve already done/ }),
    ).toBeInTheDocument()
  })

  it('says what actually separates a day hike from a trip', () => {
    // Not the duration - whether the walk has one mile axis. That is the whole
    // reason #928 exists, and it is the sentence a hiker chooses on.
    renderSheet()

    expect(screen.getByText(/can use as many trails as you like/i)).toBeInTheDocument()
    expect(
      screen.getByText(/follows one trail and breaks into days/i),
    ).toBeInTheDocument()
  })

  it('opens each door through its own handler', () => {
    const props = renderSheet()

    fireEvent.click(screen.getByRole('button', { name: /A day hike/ }))
    expect(props.onPickDayHike).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByRole('button', { name: /A multi-day trip/ }))
    expect(props.onPickTrip).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByRole('button', { name: /A walk I.{0,3}ve already done/ }))
    expect(props.onPickWalked).toHaveBeenCalledTimes(1)
  })

  it('closes', () => {
    const props = renderSheet()

    fireEvent.click(screen.getByRole('button', { name: /close/i }))
    expect(props.onClose).toHaveBeenCalledTimes(1)
  })
})

describe('when the phone has no trail network', () => {
  it('does not offer a day hike as a button at all', () => {
    renderSheet({ network: absent('not-in-release') })

    // A dead control teaches a hiker the app is broken. There is no button
    // here to press - LineSheet.tsx's rule, applied.
    expect(screen.queryByRole('button', { name: /A day hike/ })).not.toBeInTheDocument()
    expect(screen.getByText('A day hike')).toBeInTheDocument()
  })

  it('still offers the two doors that need no network', () => {
    renderSheet({ network: absent('not-in-release') })

    expect(screen.getByRole('button', { name: /A multi-day trip/ })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /A walk I.{0,3}ve already done/ }),
    ).toBeInTheDocument()
  })
})

describe('the sentence is true of the absence it is about (#1049)', () => {
  it('promises a connection will fix it ONLY where a connection will', () => {
    renderSheet({ network: absent('unreachable') })

    expect(screen.getByRole('note')).toHaveTextContent(/needs a connection/i)
  })

  it('promises nothing at all when the release simply has no graph', () => {
    // #1048, live on production. The graph arrives when somebody publishes
    // one, which is not something this phone can wait for - so the sentence
    // stops rather than reaching for a reassuring clause.
    renderSheet({ network: absent('not-in-release') })

    const note = screen.getByRole('note')
    expect(note).toHaveTextContent(/does not include the trail network/i)
    expect(note).not.toHaveTextContent(/sync|soon|connection|downloading/i)
  })

  it('says a refusal is a refusal, not a download still in flight', () => {
    // lib/trailGraphData.ts will not route on topology it cannot verify.
    // "Not downloaded yet" over that would be the opposite of what happened.
    for (const because of ['unverifiable', 'not-a-graph'] as const) {
      cleanup()
      renderSheet({ network: absent(because) })
      expect(screen.getByRole('note')).toHaveTextContent(/does not check out/i)
    }
  })

  it('names a build with no data source as that, rather than as a hiker state', () => {
    renderSheet({ network: absent('unconfigured') })

    expect(screen.getByRole('note')).toHaveTextContent(/no data source/i)
  })

  it('does not say there is no network while it is still looking for one', () => {
    // The first moments of every launch. Collapsing this into "there isn't
    // one" is how a door about to open reads as a door that never will.
    renderSheet({ network: { kind: 'looking' } })

    const note = screen.getByRole('note')
    expect(note).toHaveTextContent(/looking/i)
    expect(note).not.toHaveTextContent(/does not include|no data source/i)
  })

  it('never tells anybody to wait for a data sync', () => {
    // The exact string this issue is about, gone from every state.
    for (const network of [
      { kind: 'looking' } as const,
      absent('unconfigured'),
      absent('unreachable'),
      absent('not-in-release'),
      absent('unverifiable'),
      absent('not-a-graph'),
    ]) {
      cleanup()
      renderSheet({ network })
      expect(screen.getByRole('note')).not.toHaveTextContent(/data sync/i)
    }
  })
})

describe('the one absence a hiker can act on', () => {
  it('offers Try again when a connection would cure it', () => {
    const onRetryNetwork = vi.fn()
    renderSheet({ network: absent('unreachable'), onRetryNetwork })

    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetryNetwork).toHaveBeenCalledTimes(1)
  })

  it('offers it for nothing else', () => {
    // A release with no graph cannot be retried into existence, and a button
    // there would be the same false promise in a new shape.
    for (const network of [
      absent('unconfigured'),
      absent('not-in-release'),
      absent('unverifiable'),
      absent('not-a-graph'),
      { kind: 'looking' } as const,
    ]) {
      cleanup()
      renderSheet({ network, onRetryNetwork: vi.fn() })
      expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
    }
  })
})

describe('what it must not become', () => {
  it('carries no primary action of its own', () => {
    // PlanHome has exactly one (#805) and this sheet is what it opens. A
    // primary here would be a second call to action arriving by the back door.
    const { container } = render(
      <PlanKindSheet
        network={READY}
        walkedAvailable
        onPickDayHike={vi.fn()}
        onPickTrip={vi.fn()}
        onPickWalked={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    expect(container.querySelector('.plan__primary')).toBeNull()
  })

  it('says nothing about how hard or how long any of them is', () => {
    // No difficulty score, no time estimate, no comparison. The sheet is a
    // choice of shape, and a figure here would be one nothing has computed.
    const { container } = render(
      <PlanKindSheet
        network={READY}
        walkedAvailable
        onPickDayHike={vi.fn()}
        onPickTrip={vi.fn()}
        onPickWalked={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    const text = container.textContent ?? ''
    expect(text).not.toMatch(/\bmi\b|miles|hours|easy|moderate|strenuous|≈/i)
  })
})

describe('before the past-walk flow exists', () => {
  it('renders the third door as a sentence, not a dead control', () => {
    renderSheet({ walkedAvailable: false })

    expect(
      screen.queryByRole('button', { name: /A walk I.{0,3}ve already done/ }),
    ).not.toBeInTheDocument()
    expect(screen.getByText(/isn.{0,3}t built yet/i)).toBeInTheDocument()
  })
})
