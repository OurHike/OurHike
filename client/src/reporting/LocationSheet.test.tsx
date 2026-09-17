import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { LocationSheet, type LocationSheetProps } from './LocationSheet'
import { AT_THE_FIX, type FixSnapshot } from '../lib/reportLocation'

afterEach(() => {
  cleanup()
})

// The location picker as a window of its own (#1563). The picker's rows and
// words are lib/reportLocation.ts's and LocationPicker.test.tsx's; what this
// file is about is the frame - a dialog with a title and a Done, focus while
// it is up, and three ways out that all mean "close this and nothing else".

const NOW = new Date('2026-09-17T14:00:00Z')

const FIX: FixSnapshot = {
  lat: 37.35,
  lon: -80.35,
  mile: 628.4,
  accuracyM: 5,
  fixedAt: new Date(NOW.getTime() - 20_000),
}

function setup(overrides: Partial<LocationSheetProps> = {}) {
  const props: LocationSheetProps = {
    choice: AT_THE_FIX,
    fix: FIX,
    places: [],
    units: 'imperial',
    knowsTrail: true,
    onChoose: vi.fn(),
    onClose: vi.fn(),
    now: NOW,
    ...overrides,
  }
  return { props, ...render(<LocationSheet {...props} />) }
}

describe('LocationSheet', () => {
  it('is a modal dialog named "Where is this?" that takes focus on open', () => {
    setup()
    const sheet = screen.getByRole('dialog', { name: 'Where is this?' })
    expect(sheet).toHaveAttribute('aria-modal', 'true')
    // The dialog itself, never a row: a row CHANGES where a report goes.
    expect(sheet).toHaveFocus()
    // The picker inside is the shared one, so the fix row is there.
    expect(screen.getByTestId('location-picker')).toBeInTheDocument()
    expect(screen.getByTestId('location-fix')).toHaveTextContent('±16 ft · just now')
  })

  it('closes on Done, on Escape and on its scrim, without choosing anything', () => {
    const { props, unmount } = setup()
    fireEvent.click(screen.getByTestId('location-sheet-done'))
    expect(props.onClose).toHaveBeenCalledTimes(1)
    expect(props.onChoose).not.toHaveBeenCalled()
    unmount()

    const second = setup()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(second.props.onClose).toHaveBeenCalledTimes(1)
    second.unmount()

    const third = setup()
    fireEvent.click(screen.getByTestId('location-sheet-scrim'))
    expect(third.props.onClose).toHaveBeenCalledTimes(1)
    // A tap on the sheet itself is not a tap on the scrim.
    fireEvent.click(screen.getByTestId('location-sheet'))
    expect(third.props.onClose).toHaveBeenCalledTimes(1)
  })

  it('keeps a tap on its scrim from reaching whatever is under it', () => {
    // The report window renders this inside its own scrim, whose click
    // closes the whole window; the closure form and the long form have a
    // Cancel under it. None of them may hear a tap meant for this sheet.
    const under = vi.fn()
    const props: LocationSheetProps = {
      choice: AT_THE_FIX,
      fix: FIX,
      places: [],
      units: 'imperial',
      knowsTrail: true,
      onChoose: vi.fn(),
      onClose: vi.fn(),
      now: NOW,
    }
    render(
      <div onClick={under}>
        <LocationSheet {...props} />
      </div>,
    )
    fireEvent.click(screen.getByTestId('location-sheet-scrim'))
    fireEvent.click(screen.getByTestId('location-sheet-done'))
    expect(props.onClose).toHaveBeenCalledTimes(2)
    expect(under).not.toHaveBeenCalled()
  })

  it('returns focus to whatever opened it when it closes', () => {
    // The long form and the closure form have no focus management of their
    // own, so without this a closed sheet dropped focus to the body and the
    // next Tab started from the top of the page (review of #1571).
    const opener = document.createElement('button')
    document.body.appendChild(opener)
    opener.focus()
    const { unmount } = setup()
    expect(screen.getByTestId('location-sheet')).toHaveFocus()
    unmount()
    expect(opener).toHaveFocus()
    opener.remove()
  })

  it('hands a row to onChoose exactly as the picker would', () => {
    const { props } = setup()
    fireEvent.click(screen.getByTestId('location-fix'))
    expect(props.onChoose).toHaveBeenCalledWith(AT_THE_FIX)
  })

  it('loops Tab inside itself', () => {
    setup({ places: [], onSearch: () => [] })
    const focusable = screen
      .getByTestId('location-sheet')
      .querySelectorAll<HTMLElement>('button, input, textarea')
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (first === undefined || last === undefined) throw new Error('no controls')

    last.focus()
    fireEvent.keyDown(document, { key: 'Tab' })
    expect(first).toHaveFocus()

    first.focus()
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })
    expect(last).toHaveFocus()
  })
})
