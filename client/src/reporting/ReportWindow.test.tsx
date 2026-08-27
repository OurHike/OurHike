import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent, act } from '@testing-library/react'
import { ReportWindow, UNDO_WINDOW_MS, type ReportWindowProps } from './ReportWindow'
import { EMERGENCY_NOTICE } from './categories'
import { MAX_UNDO_HOLD_MS } from '../lib/outbox'

afterEach(() => {
  cleanup()
})

// The report window (#1133). The load-bearing behaviours, in the order they
// would hurt somebody if they broke:
//
//   - the two that must never file on a tap, never file on a tap
//   - the 911 line is readable BEFORE the tap, and is the shipped words
//   - a tap really does file, and Undo really does take it back
//   - the undo window is shorter than the outbox's own ceiling on holds
//
// Everything else here is ordinary UI.

const NOW = new Date('2026-08-27T07:42:00Z')

function setup(overrides: Partial<ReportWindowProps> = {}) {
  const props: ReportWindowProps = {
    anchor: { label: 'mi 628.4', phrase: 'at mi 628.4', mile: 628.4 },
    reporterType: 'thru',
    onFile: vi.fn().mockResolvedValue('outbox-1'),
    onUndo: vi.fn().mockResolvedValue(undefined),
    onReportClosure: vi.fn(),
    onReportUnsafe: vi.fn(),
    onClose: vi.fn(),
    now: NOW,
    ...overrides,
  }
  return { props, ...render(<ReportWindow {...props} />) }
}

describe('what the window offers', () => {
  it('draws the six that file on a tap, under the corrected constants', () => {
    setup()
    // `invasive_species`, not the handoff's `invasive`. `shelter_repair` keeps
    // its constant while its label broadens.
    for (const id of [
      'blowdown',
      'flooding',
      'trash',
      'shelter_repair',
      'animals',
      'invasive_species',
    ]) {
      expect(screen.getByTestId(`report-tile-${id}`)).toBeTruthy()
    }
    expect(screen.getByTestId('report-tile-shelter_repair')).toHaveTextContent(
      'Shelter or campsite',
    )
  })

  it('gives every tile a description, not just the two that used to have one', () => {
    setup()
    // "Trash" is the one that gives the old inconsistency away: litter a hiker
    // can pack out, or a bin that needs a crew with a truck?
    expect(screen.getByTestId('report-tile-trash')).toHaveTextContent(
      'Litter, dumped gear, an overflowing bin',
    )
    expect(screen.getByTestId('report-tile-blowdown')).toHaveTextContent(
      'A tree down across the trail',
    )
  })
})

describe('the two that must never file on a tap', () => {
  it('sends a closure out of this flow entirely, filing nothing', () => {
    // #832: a closure is a stretch with two ends and its own table, not an
    // eighth report type. It is not even in the union - categories.ts gives
    // CLOSURE_ROW no `id` - so there is nothing here that COULD be filed.
    const { props } = setup()

    fireEvent.click(screen.getByTestId('report-row-closure'))

    expect(props.onReportClosure).toHaveBeenCalledTimes(1)
    expect(props.onFile).not.toHaveBeenCalled()
  })

  it('sends an unsafe encounter to the long form, filing nothing', () => {
    // Private to club moderators, never a public pin, and never something that
    // lands in a queue because a thumb brushed a tile.
    const { props } = setup()

    fireEvent.click(screen.getByTestId('report-row-unsafe'))

    expect(props.onReportUnsafe).toHaveBeenCalledTimes(1)
    expect(props.onFile).not.toHaveBeenCalled()
  })

  it('says how to get real help before the tap, in the words that shipped', () => {
    // Before, not after: somebody in trouble right now needs to know this is
    // the wrong tool while they can still act on that, rather than once they
    // are already in a form. The copy is verbatim from ReportTypePicker and
    // this is what holds it there.
    setup()

    const notice = screen.getByRole('note')
    expect(notice).toHaveTextContent(
      'Call 911 if you are in danger now. This reaches volunteers, sometimes days later.',
    )
    expect(EMERGENCY_NOTICE).toBe(notice.textContent)
  })
})

describe('filing on the tap', () => {
  it('writes the report immediately and shows what it wrote', async () => {
    const { props } = setup()

    await act(async () => {
      fireEvent.click(screen.getByTestId('report-tile-blowdown'))
    })

    expect(props.onFile).toHaveBeenCalledTimes(1)
    const [type, note, holdUntil] = vi.mocked(props.onFile).mock.calls[0] ?? []
    expect(type).toBe('blowdown')
    expect(note).toBe('')
    expect(holdUntil).toBeInstanceOf(Date)

    expect(screen.getByRole('status')).toHaveTextContent('Filed — blow down at mi 628.4')
    // And the tiles are gone: there is nothing left to tap by accident on a
    // surface that files on taps.
    expect(screen.queryByTestId('report-tile-flooding')).toBeNull()
  })

  it('does not say “at here”', async () => {
    // THE FIRST PHOTOGRAPH OF THIS SCREEN CAUGHT THIS, and no test had.
    // Every case above uses a mile anchor, where composing `at ${label}` reads
    // perfectly - and a build with no GPS fix anchors to "here", where it
    // reads "Filed — blow down at here". "here" is an adverb; the other two
    // forms are nouns. So the window takes the finished phrase rather than
    // building one, and this is the case that says why.
    setup({ anchor: { label: 'here', phrase: 'here' } })

    await act(async () => {
      fireEvent.click(screen.getByTestId('report-tile-blowdown'))
    })

    expect(screen.getByRole('status')).toHaveTextContent('Filed — blow down here')
    expect(screen.getByRole('status')).not.toHaveTextContent('at here')
  })

  it('holds it back for less than the outbox is willing to hold anything', () => {
    // The two constants live in different files and have to agree: a window
    // longer than lib/outbox.ts's ceiling would produce a countdown still
    // running over a report that has already gone. This is the assertion that
    // makes the ceiling mean something.
    expect(UNDO_WINDOW_MS).toBeLessThan(MAX_UNDO_HOLD_MS)
  })

  it('carries a note typed before the tap', async () => {
    // Not the ordinary path - the note lives under the receipt - but the state
    // is shared, and a note that silently failed to travel would be somebody's
    // words dropped.
    const { props } = setup()
    await act(async () => {
      fireEvent.click(screen.getByTestId('report-tile-flooding'))
    })
    fireEvent.change(screen.getByTestId('report-note'), {
      target: { value: 'Knee-deep at the ford.' },
    })
    fireEvent.click(screen.getByTestId('report-again'))
    await act(async () => {
      fireEvent.click(screen.getByTestId('report-tile-blowdown'))
    })

    // Cleared by "Note something else", because it described the report that
    // was just filed. Attaching it to the next one would be somebody's words
    // on the wrong thing.
    expect(vi.mocked(props.onFile).mock.calls[1]?.[1]).toBe('')
  })
})

describe('undo', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('takes the report back out of the queue by its own id', async () => {
    const { props } = setup()

    await act(async () => {
      fireEvent.click(screen.getByTestId('report-tile-blowdown'))
    })
    await act(async () => {
      fireEvent.click(screen.getByTestId('report-undo'))
    })

    // The id `onFile` handed back - which is the outbox's own, so undo is
    // `removeQueued` and not a second withdrawal path.
    expect(props.onUndo).toHaveBeenCalledWith('outbox-1')
    // And back to the tiles, ready for the right one.
    expect(screen.getByTestId('report-tile-blowdown')).toBeTruthy()
  })

  it('stops offering itself once the window has run out', async () => {
    setup()

    await act(async () => {
      fireEvent.click(screen.getByTestId('report-tile-blowdown'))
    })
    expect(screen.getByTestId('report-undo')).toBeTruthy()

    await act(async () => {
      vi.advanceTimersByTime(UNDO_WINDOW_MS + 500)
    })

    // Gone rather than disabled: a control that is present and does nothing is
    // the thing this whole mechanism exists to avoid.
    expect(screen.queryByTestId('report-undo')).toBeNull()
    // The report stands, and the receipt still says so.
    expect(screen.getByRole('status')).toHaveTextContent('Filed —')
  })

  it('counts down in whole seconds', async () => {
    setup()
    await act(async () => {
      fireEvent.click(screen.getByTestId('report-tile-blowdown'))
    })
    expect(screen.getByTestId('report-undo')).toHaveTextContent('Undo · 8s')

    await act(async () => {
      vi.advanceTimersByTime(3_000)
    })
    expect(screen.getByTestId('report-undo')).toHaveTextContent('Undo · 5s')
  })
})

describe('getting out', () => {
  it('tells the caller nothing was filed, so nothing is asked of the hiker', () => {
    // Somebody who opened the window, read it and closed it has not
    // contributed anything, and must not be asked to sign in for it. The old
    // two-screen flow could not get this wrong - reaching its save path meant
    // submitting a form - and a window you can open and close for free can.
    const onClose = vi.fn()
    setup({ onClose })

    fireEvent.click(screen.getByTestId('report-close'))

    expect(onClose).toHaveBeenCalledWith(false)
  })

  it('tells the caller when something IS standing', async () => {
    const onClose = vi.fn()
    setup({ onClose })

    await act(async () => {
      fireEvent.click(screen.getByTestId('report-tile-blowdown'))
    })
    fireEvent.click(screen.getByTestId('report-done'))

    expect(onClose).toHaveBeenCalledWith(true)
  })

  it('counts an undone report as nothing filed', async () => {
    // The case a boolean flag would get wrong. Filed then taken back is not a
    // contribution, and there is nothing in the queue to sign for.
    const onClose = vi.fn()
    setup({ onClose })

    await act(async () => {
      fireEvent.click(screen.getByTestId('report-tile-blowdown'))
    })
    await act(async () => {
      fireEvent.click(screen.getByTestId('report-undo'))
    })
    fireEvent.click(screen.getByTestId('report-close'))

    expect(onClose).toHaveBeenCalledWith(false)
  })

  it('closes on the close button, on Escape, and on the scrim', () => {
    const onClose = vi.fn()
    setup({ onClose })

    fireEvent.click(screen.getByTestId('report-close'))
    fireEvent.keyDown(document, { key: 'Escape' })
    fireEvent.click(screen.getByTestId('report-window-scrim'))

    expect(onClose).toHaveBeenCalledTimes(3)
  })

  it('does not close when the window itself is tapped', () => {
    // The scrim's click handler is on the parent, so without the dialog
    // stopping propagation every tap on a tile would also close the window -
    // which under 1a means filing a report and immediately hiding the Undo.
    const onClose = vi.fn()
    setup({ onClose })

    fireEvent.click(screen.getByTestId('report-window'))

    expect(onClose).not.toHaveBeenCalled()
  })

  it('is a modal dialog that names itself', () => {
    setup()
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    // Named by its own heading rather than by a hardcoded label, so the two
    // cannot come to disagree.
    expect(dialog).toHaveAccessibleName('What did you find?')
  })

  it('gives focus back to whatever opened it', () => {
    // Four entry points open this window. Returning focus here rather than
    // asking each of them to remember is what stops a keyboard user landing at
    // the top of the document every time they close it.
    const opener = document.createElement('button')
    document.body.appendChild(opener)
    opener.focus()
    expect(document.activeElement).toBe(opener)

    const { unmount } = setup()
    expect(document.activeElement).not.toBe(opener)

    unmount()
    expect(document.activeElement).toBe(opener)
    opener.remove()
  })

  it('does not open with focus already on a control that files', () => {
    // Under 1a the first tile is a control that WRITES A REPORT, and a
    // keystroke into it is not recoverable with Escape. The dialog takes focus
    // instead, which is also what makes the trap work from the first Tab.
    setup()
    expect(document.activeElement).toBe(screen.getByTestId('report-window'))
  })
})
