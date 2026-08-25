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

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { PlanKindSheet } from './PlanKindSheet'

// This suite renders the same sheet many times; the repo's convention is an
// explicit cleanup rather than relying on a global one.
afterEach(() => {
  cleanup()
})

function renderSheet(overrides: Partial<Parameters<typeof PlanKindSheet>[0]> = {}) {
  const props = {
    networkAvailable: true,
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
    renderSheet({ networkAvailable: false })

    // A dead control teaches a hiker the app is broken. There is no button
    // here to press - LineSheet.tsx's rule, applied.
    expect(screen.queryByRole('button', { name: /A day hike/ })).not.toBeInTheDocument()
    expect(screen.getByText('A day hike')).toBeInTheDocument()
  })

  it('says what is missing and when it arrives', () => {
    renderSheet({ networkAvailable: false })

    expect(screen.getByRole('note')).toHaveTextContent(/trail network/i)
    expect(screen.getByRole('note')).toHaveTextContent(/next data sync/i)
  })

  it('still offers the two doors that need no network', () => {
    renderSheet({ networkAvailable: false })

    expect(screen.getByRole('button', { name: /A multi-day trip/ })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /A walk I.{0,3}ve already done/ }),
    ).toBeInTheDocument()
  })
})

describe('what it must not become', () => {
  it('carries no primary action of its own', () => {
    // PlanHome has exactly one (#805) and this sheet is what it opens. A
    // primary here would be a second call to action arriving by the back door.
    const { container } = render(
      <PlanKindSheet
        networkAvailable
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
        networkAvailable
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
