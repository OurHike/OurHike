import { describe, it, expect, vi, afterEach, beforeEach, beforeAll } from 'vitest'
import { render, screen, cleanup, fireEvent, act } from '@testing-library/react'
import { ReportWindow, type ReportWindowProps } from './ReportWindow'
import { UNDO_WINDOW_MS } from './undoWindow'
import { preloadScreens } from '../screens/deferred'
import { EMERGENCY_NOTICE } from './categories'
import { MAX_UNDO_HOLD_MS } from '../lib/outbox'
import {
  AT_THE_FIX,
  STALE_FIX_SECONDS,
  type FixSnapshot,
  type NearbyPlace,
} from '../lib/reportLocation'

// The sheet and the reporter block are deferred (screens/deferred.ts);
// loaded ahead so they render synchronously here, as they do in the shell.
beforeAll(() => preloadScreens())

afterEach(() => {
  cleanup()
})

// The report window (#1133). The load-bearing behaviours, in the order they
// would hurt somebody if they broke:
//
//   - closure and unsafe-encounter rows call their own handler, never onFile
//   - the 911 notice renders EMERGENCY_NOTICE verbatim, before any tap
//   - a tap calls onFile, and Undo calls onUndo with the id it returned
//   - UNDO_WINDOW_MS stays under lib/outbox.ts's MAX_UNDO_HOLD_MS
//
// Everything else here is ordinary UI.

const NOW = new Date('2026-08-27T07:42:00Z')

/** A fix at mi 628.4, twenty seconds old, ±5 m - what "here" resolves to. */
const FIX: FixSnapshot = {
  lat: 37.35,
  lon: -80.35,
  mile: 628.4,
  accuracyM: 5,
  fixedAt: new Date(NOW.getTime() - 20_000),
}

const PLACES: NearbyPlace[] = [
  {
    id: 'p-near',
    name: 'Niday Shelter',
    type: 'shelter',
    mile: 627.8,
    lat: 37.3,
    lon: -80.3,
    awayMiles: 0.6,
  },
  {
    id: 'p-mid',
    name: 'Craig Creek',
    type: 'water',
    mile: 624.0,
    lat: 37.35,
    lon: -80.35,
    awayMiles: 1.2,
  },
]

function setup(overrides: Partial<ReportWindowProps> = {}) {
  const props: ReportWindowProps = {
    location: AT_THE_FIX,
    fix: FIX,
    places: [],
    knowsTrail: true,
    onChooseLocation: vi.fn(),
    units: 'imperial',
    reporterType: 'thru',
    names: { trail: 'Switchback', real: null },
    onRealName: vi.fn(),
    onFile: vi.fn().mockResolvedValue('outbox-1'),
    onAmend: vi.fn().mockResolvedValue(true),
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
  it('draws all six filing tiles, including invasive_species and shelter_repair', () => {
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

  it('gives every tile a description, trash and blowdown included', () => {
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
  it('calls onReportClosure for a closure, and never onFile', () => {
    // #832: a closure is a stretch with two ends and its own table, not an
    // eighth report type. It is not even in the union - categories.ts gives
    // CLOSURE_ROW no `id` - so there is nothing here that COULD be filed.
    const { props } = setup()

    fireEvent.click(screen.getByTestId('report-row-closure'))

    expect(props.onReportClosure).toHaveBeenCalledTimes(1)
    expect(props.onFile).not.toHaveBeenCalled()
  })

  it('calls onReportUnsafe for an unsafe encounter, and never onFile', () => {
    // Private to club moderators, never a public pin, and never something that
    // lands in a queue because a thumb brushed a tile.
    const { props } = setup()

    fireEvent.click(screen.getByTestId('report-row-unsafe'))

    expect(props.onReportUnsafe).toHaveBeenCalledTimes(1)
    expect(props.onFile).not.toHaveBeenCalled()
  })

  it('renders EMERGENCY_NOTICE verbatim, before any tile is tapped', () => {
    // Before, not after: somebody in trouble right now needs to know this is
    // the wrong tool while they can still act on that, rather than once they
    // are already in a form. The copy came over unchanged from the retired
    // picker route (categories.ts's EMERGENCY_NOTICE says where from), and
    // the literal below is what holds it there - spelled out rather than
    // compared to the constant alone, so an edit to the constant fails here
    // instead of quietly agreeing with itself.
    setup()

    const notice = screen.getByRole('note')
    expect(notice).toHaveTextContent(
      'Call 911 if you are in danger now. This reaches volunteers, sometimes days later.',
    )
    expect(EMERGENCY_NOTICE).toBe(notice.textContent)
  })

  it('keeps the 911 note outside .report-window__body, and before it', () => {
    // #1480, and the assertion this file was missing when the maintainer
    // photographed the defect. "Before the tap" was tested as document order
    // within the body, which the notice satisfied while sitting 39 px below
    // the fold on a 390x844 phone and 190 px below it on a 360x640 one - the
    // test passed and nobody could read the line.
    //
    // jsdom has no layout, so this cannot assert pixels. It asserts the thing
    // that MAKES the pixels right and that a future change would have to
    // undo deliberately: the notice is not inside the scrolling element, and
    // it precedes it. A category added to the grid can then push nothing but
    // other categories.
    setup()

    const notice = screen.getByRole('note')
    const body = document.querySelector('.report-window__body')

    expect(body).not.toBeNull()
    expect(body?.contains(notice)).toBe(false)
    // DOCUMENT_POSITION_FOLLOWING: the body comes after the notice, so the
    // notice is read first by a screen reader and drawn first on the glass.
    expect(notice.compareDocumentPosition(body as Node)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    )
  })

  it('removes the 911 note once a report is filed', async () => {
    // Unchanged by #1480 and worth holding down now that it could drift.
    // While the tiles are up the line is guidance about a choice somebody is
    // ABOUT to make; after a tap the body is a receipt for a report that is
    // already filed. Pinning it outside the body made "it renders whenever
    // the window does" the easy mistake, so this is the test that would catch
    // it.
    setup()
    expect(screen.getByRole('note')).toBeTruthy()

    await act(async () => {
      fireEvent.click(screen.getByTestId('report-tile-blowdown'))
    })

    expect(screen.getByRole('status')).toHaveTextContent('Filed — blow down')
    expect(screen.queryByRole('note')).toBeNull()
  })
})

describe('filing on the tap', () => {
  it('calls onFile on the tap and shows "Filed — blow down at mi 628.4"', async () => {
    const { props } = setup()

    await act(async () => {
      fireEvent.click(screen.getByTestId('report-tile-blowdown'))
    })

    expect(props.onFile).toHaveBeenCalledTimes(1)
    const [type, note, holdUntil, extras] = vi.mocked(props.onFile).mock.calls[0] ?? []
    expect(type).toBe('blowdown')
    expect(note).toBe('')
    expect(holdUntil).toBeInstanceOf(Date)
    // No words: the fix placed it, and the shell sends words only when
    // nothing else can (lib/reportLocation.ts). Signed with the trail name
    // and not contactable, because nothing was asked before the tap.
    expect(extras).toEqual({
      location: AT_THE_FIX,
      placeWords: '',
      signature: { kind: 'trail', name: 'Switchback' },
      contactOk: false,
    })

    expect(screen.getByRole('status')).toHaveTextContent('Filed — blow down at mi 628.4')
    // And the tiles are gone: there is nothing left to tap by accident on a
    // surface that files on taps.
    expect(screen.queryByTestId('report-tile-flooding')).toBeNull()
  })

  it('says "Filed — blow down here" for a fix with no mile, never "at here"', async () => {
    // THE FIRST PHOTOGRAPH OF THIS SCREEN CAUGHT THIS, and no test had.
    // Every case above uses a fix with a mile, where composing `at ${label}`
    // reads perfectly - and a fix off the corridor resolves to "here", where
    // it would read "Filed — blow down at here". "here" is an adverb; the
    // other forms are nouns. So lib/reportLocation.ts hands over the finished
    // phrase rather than the window building one, and this is the case that
    // says why.
    const { mile: _offCorridor, ...noMile } = FIX
    setup({ fix: noMile })

    await act(async () => {
      fireEvent.click(screen.getByTestId('report-tile-blowdown'))
    })

    expect(screen.getByRole('status')).toHaveTextContent('Filed — blow down here')
    expect(screen.getByRole('status')).not.toHaveTextContent('at here')
  })

  it('keeps UNDO_WINDOW_MS under the outbox MAX_UNDO_HOLD_MS ceiling', () => {
    // The two constants live in different files and have to agree: a window
    // longer than lib/outbox.ts's ceiling would produce a countdown still
    // running over a report that has already gone. This is the assertion that
    // makes the ceiling mean something.
    expect(UNDO_WINDOW_MS).toBeLessThan(MAX_UNDO_HOLD_MS)
  })

  it('clears the note when "Note something else" starts a second report', async () => {
    // The note lives under the receipt, so it is typed AFTER a report is
    // filed and describes that one. "Note something else" starts a second
    // report, and the state is shared - so the question is whether the first
    // note travels, and it must not: somebody's words on the wrong report.
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

  it('calls onUndo with the id onFile returned', async () => {
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

  it('removes the Undo control after UNDO_WINDOW_MS, rather than disabling it', async () => {
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

  it('counts the Undo label down in whole seconds', async () => {
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
  it('calls onClose(false) when the window closes with nothing filed', () => {
    // Somebody who opened the window, read it and closed it has not
    // contributed anything, and must not be asked to sign in for it. The old
    // two-screen flow could not get this wrong - reaching its save path meant
    // submitting a form - and a window you can open and close for free can.
    const onClose = vi.fn()
    setup({ onClose })

    fireEvent.click(screen.getByTestId('report-close'))

    expect(onClose).toHaveBeenCalledWith(false)
  })

  it('calls onClose(true) when a filed report stands', async () => {
    const onClose = vi.fn()
    setup({ onClose })

    await act(async () => {
      fireEvent.click(screen.getByTestId('report-tile-blowdown'))
    })
    fireEvent.click(screen.getByTestId('report-done'))

    expect(onClose).toHaveBeenCalledWith(true)
  })

  it('calls onClose(false) after a report is filed then undone', async () => {
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

  it('is aria-modal, named by its own heading', () => {
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

// Re-anchoring: the picker behind the header's `Change`.
//
// The report a hiker files is only as useful as the place it names, and the
// one case this window's stated anchor gets wrong is the common one on a long
// day: a blow-down climbed over, then remembered at the next water stop. What
// the tests below hold is that the way back to it is honest - offered only
// when it leads somewhere, ordered by what a hiker is actually thinking in,
// and silent about how many places they walked past without reporting.
describe('changing where the report lands (#1563)', () => {
  it('states the fix in the header as its mile, and offers Change', () => {
    setup()

    expect(screen.getByTestId('report-anchor')).toHaveTextContent('mi 628.4')
    // A fresh, tight fix gets no second line: the line costs height the tile
    // frame does not have at 375x667 (#1480 - CI on WebKit measured the body
    // scrolling by 7 px with it always drawn), and the radius and age are one
    // tap away in the picker's own row.
    expect(screen.queryByTestId('report-anchor-detail')).toBeNull()
    // OFFERED WHATEVER THE PLACES LIST HOLDS, which is the change from the
    // passed-places control this replaces: the picker always has the words
    // and the map to offer, so there is no empty list to open onto.
    expect(screen.getByTestId('report-change-anchor')).toBeInTheDocument()
    expect(screen.queryByTestId('location-sheet')).toBeNull()
  })

  it('spends a line under the place on a fix that is stale or coarse, with the words a hiker should hesitate over', () => {
    const { unmount } = setup({
      fix: { ...FIX, fixedAt: new Date(NOW.getTime() - (STALE_FIX_SECONDS + 30) * 1000) },
    })
    expect(screen.getByTestId('report-anchor-detail')).toHaveTextContent(
      'Your position · ±16 ft · 5 min ago — you may have moved since',
    )
    unmount()

    setup({ fix: { ...FIX, accuracyM: 250 } })
    expect(screen.getByTestId('report-anchor-detail')).toHaveTextContent(
      '±820 ft · just now',
    )
  })

  it('refuses a tap with nothing to place the report at, opening the sheet with the reason, and files once answered', async () => {
    // THE GAP THIS CHANGE CLOSES. No fix, no card, no press: the old window
    // filed a blowdown here with no location of any kind. Now the tap is
    // refused, the sheet opens saying why, and the tile files once the hiker
    // has said where - in words, when there is nothing else.
    const { props } = setup({ fix: null })

    expect(screen.getByTestId('report-anchor')).toHaveTextContent('No location yet')
    // Nothing opens by itself: the sheet is modal, and the tiles come first.
    expect(screen.queryByTestId('location-sheet')).toBeNull()

    await act(async () => {
      fireEvent.click(screen.getByTestId('report-tile-blowdown'))
    })
    expect(props.onFile).not.toHaveBeenCalled()
    // A window of its own over the tiles (reporting/LocationSheet.tsx), and
    // it has focus: the refusal is heard as well as seen.
    expect(screen.getByTestId('location-sheet')).toHaveFocus()
    expect(screen.getByRole('alert')).toHaveTextContent('Say where this is first')
    expect(screen.queryByTestId('report-undo')).toBeNull()

    fireEvent.change(screen.getByTestId('location-words'), {
      target: { value: 'the ford below the gap' },
    })
    // Done closes the sheet with the words kept, and the tap that was
    // refused files by itself: the category is asked once (the
    // maintainer's steer of 2026-09-17), and the receipt's Undo is the
    // hiker's way back.
    await act(async () => {
      fireEvent.click(screen.getByTestId('location-sheet-done'))
    })
    expect(screen.queryByTestId('location-sheet')).toBeNull()
    expect(screen.getByTestId('report-anchor')).toHaveTextContent('In your words')

    expect(props.onFile).toHaveBeenCalledTimes(1)
    expect(vi.mocked(props.onFile).mock.calls[0]?.[0]).toBe('blowdown')
    expect(vi.mocked(props.onFile).mock.calls[0]?.[3]?.placeWords).toBe(
      'the ford below the gap',
    )
    expect(screen.getByRole('status')).toHaveTextContent(
      'Filed — blow down where you described',
    )
  })

  it('hands a chosen place to the shell and closes the picker', () => {
    const onChooseLocation = vi.fn()
    setup({ places: PLACES, onChooseLocation })
    fireEvent.click(screen.getByTestId('report-change-anchor'))
    fireEvent.click(screen.getByTestId('location-place-p-mid'))

    // The whole place, coordinates included: an anchor needs a lat and a
    // lon, and the alternative to carrying them is inventing them at pick
    // time. The shell owns the answer, so the window asks rather than
    // deciding - it does not re-label itself until the prop comes back.
    expect(onChooseLocation).toHaveBeenCalledWith({
      kind: 'poi',
      poiId: 'p-mid',
      name: 'Craig Creek',
      lat: 37.35,
      lon: -80.35,
      mile: 624.0,
    })
    expect(screen.queryByTestId('location-sheet')).toBeNull()
  })

  it('states a named place, and files under its phrase', async () => {
    const { props } = setup({
      location: {
        kind: 'poi',
        poiId: 'p-near',
        name: 'Niday Shelter',
        lat: 37.3,
        lon: -80.3,
        mile: 627.8,
      },
    })
    expect(screen.getByTestId('report-anchor')).toHaveTextContent('Niday Shelter')
    // The name says what it is; no second line.
    expect(screen.queryByTestId('report-anchor-detail')).toBeNull()

    await act(async () => {
      fireEvent.click(screen.getByTestId('report-tile-trash'))
    })

    expect(props.onFile).toHaveBeenCalled()
    expect(screen.getByRole('status')).toHaveTextContent('Filed — trash at Niday Shelter')
  })

  it('offers the map only when the shell has one to aim at, and closes the picker on a kept point', () => {
    const { rerender, props } = setup({ onPointOnMap: vi.fn() })
    fireEvent.click(screen.getByTestId('report-change-anchor'))
    fireEvent.click(screen.getByTestId('location-map'))
    expect(props.onPointOnMap).toHaveBeenCalled()

    // The shell answers Keep by changing the location. The window sees the
    // new prop, closes the picker, and states the marked spot.
    rerender(
      <ReportWindow
        {...props}
        location={{ kind: 'point', lat: 37.4, lon: -80.4, mile: 630 }}
      />,
    )
    expect(screen.queryByTestId('location-sheet')).toBeNull()
    expect(screen.getByTestId('report-anchor')).toHaveTextContent('mi 630.0')
    expect(screen.queryByTestId('report-anchor-detail')).toBeNull()
  })

  it('stands aside for the crosshair: hidden, inert, and deaf to Escape', () => {
    const onClose = vi.fn()
    setup({ standingAside: true, onClose })

    const scrim = screen.getByTestId('report-window-scrim')
    expect(scrim).toHaveClass('report-window__scrim--stood-aside')
    expect(scrim.hasAttribute('inert')).toBe(true)

    // An Escape meant for the pick bar must not close a window the hiker
    // cannot see.
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).not.toHaveBeenCalled()
  })

  it('closes the sheet on Escape, and the window only on the second one', async () => {
    // THE REFLEX THIS PROTECTS. Escape is how a person backs out of a list,
    // and closing the whole window from inside one would lose the screen
    // behind it - the single thing this change exists to prevent. The search
    // box compounds it: `<input type="search">` clears itself on Escape in
    // WebKit and Blink, so somebody expecting an empty field would instead
    // lose the window.
    const onClose = vi.fn()
    setup({ places: PLACES, onClose })
    fireEvent.click(screen.getByTestId('report-change-anchor'))
    expect(screen.getByTestId('location-sheet')).toBeTruthy()

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByTestId('location-sheet')).toBeNull()
    expect(onClose).not.toHaveBeenCalled()

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })

  it('forgets a typed search when the sheet is dismissed', async () => {
    // Reopening onto somebody's abandoned three letters is a list that looks
    // short for a reason nobody can see.
    setup({ places: PLACES, onSearchPlaces: () => [] })
    fireEvent.click(screen.getByTestId('report-change-anchor'))
    fireEvent.change(screen.getByTestId('location-search'), {
      target: { value: 'Craig' },
    })
    fireEvent.keyDown(document, { key: 'Escape' })

    fireEvent.click(screen.getByTestId('report-change-anchor'))
    expect(screen.getByTestId('location-search')).toHaveValue('')
    expect(screen.getByTestId('location-place-p-near')).toBeTruthy()
  })

  it('takes Change away once the report is filed', async () => {
    // After a tap the window is a receipt, and the report it describes is
    // already in the outbox at the place it was filed with. Re-placing from
    // here would move a record that has already been written.
    setup({ places: PLACES })
    expect(screen.getByTestId('report-change-anchor')).toBeTruthy()

    fireEvent.click(screen.getByTestId('report-tile-blowdown'))
    await screen.findByTestId('report-undo')

    expect(screen.queryByTestId('report-change-anchor')).toBeNull()
    expect(screen.queryByTestId('report-anchor-detail')).toBeNull()
  })
})

describe('the sheet over the window (#1563)', () => {
  it('is a dialog of its own that Done closes without closing the window', () => {
    const onClose = vi.fn()
    setup({ places: PLACES, onClose })
    fireEvent.click(screen.getByTestId('report-change-anchor'))

    const sheet = screen.getByTestId('location-sheet')
    expect(sheet).toHaveAttribute('role', 'dialog')
    expect(sheet).toHaveTextContent('Where is this?')
    expect(sheet).toHaveFocus()
    // The picker is the same one the long form renders, inside it.
    expect(screen.getByTestId('location-picker')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('location-sheet-done'))
    expect(screen.queryByTestId('location-sheet')).toBeNull()
    expect(onClose).not.toHaveBeenCalled()
    // Focus comes back to the window, and to the dialog rather than a tile.
    expect(screen.getByTestId('report-window')).toHaveFocus()
  })

  it('does not let a tap on its own scrim reach the scrim under it', () => {
    // The sheet sits inside the window's scrim, whose click closes the whole
    // window. A tap beside the sheet must close the sheet and nothing else.
    const onClose = vi.fn()
    setup({ places: PLACES, onClose })
    fireEvent.click(screen.getByTestId('report-change-anchor'))
    fireEvent.click(screen.getByTestId('location-sheet-scrim'))

    expect(screen.queryByTestId('location-sheet')).toBeNull()
    expect(onClose).not.toHaveBeenCalled()
  })
})

describe('the receipt writes back (#1563)', () => {
  /** Files a blowdown and waits for the receipt. */
  async function filed(overrides: Partial<ReportWindowProps> = {}) {
    const result = setup(overrides)
    await act(async () => {
      fireEvent.click(screen.getByTestId('report-tile-blowdown'))
    })
    await screen.findByTestId('report-note')
    return result
  }

  it('writes the note to the filed report at Done, and only then closes', async () => {
    // "Add detail - optional" used to be a textarea nothing read.
    const { props } = await filed()
    fireEvent.change(screen.getByTestId('report-note'), {
      target: { value: '  Big oak, step over the top.  ' },
    })
    expect(props.onAmend).not.toHaveBeenCalled()

    await act(async () => {
      fireEvent.click(screen.getByTestId('report-done'))
    })

    expect(props.onAmend).toHaveBeenCalledWith(
      'outbox-1',
      expect.objectContaining({ note: 'Big oak, step over the top.' }),
    )
    expect(props.onClose).toHaveBeenCalledWith(true)
  })

  it('writes nothing at Done when no note was typed', async () => {
    const { props } = await filed()
    await act(async () => {
      fireEvent.click(screen.getByTestId('report-done'))
    })
    expect(props.onAmend).not.toHaveBeenCalled()
    expect(props.onClose).toHaveBeenCalledWith(true)
  })

  it('says so and stays open once when the report had already sent, then closes', async () => {
    // A note the hiker believes is attached and is not would be a confident
    // wrong display; the window says it instead, once, and the second Done
    // closes because there is nothing left it can do.
    const { props } = await filed({ onAmend: vi.fn().mockResolvedValue(false) })
    fireEvent.change(screen.getByTestId('report-note'), {
      target: { value: 'the ford was waist deep' },
    })
    await act(async () => {
      fireEvent.click(screen.getByTestId('report-done'))
    })

    expect(screen.getByTestId('report-lost')).toHaveTextContent('had already sent')
    expect(props.onClose).not.toHaveBeenCalled()

    await act(async () => {
      fireEvent.click(screen.getByTestId('report-done'))
    })
    expect(props.onClose).toHaveBeenCalledWith(true)
  })

  it('signs with the trail name by default, and writes a change of name or consent to the report as it is made', async () => {
    const { props } = await filed()
    expect(screen.getByTestId('report-signature')).toHaveTextContent(
      'Signed as Switchback (trail name) · thru',
    )

    // The consent, written at once rather than at Done: a receipt left open
    // still carries it.
    await act(async () => {
      fireEvent.click(screen.getByTestId('reporter-contact-ok'))
    })
    expect(props.onAmend).toHaveBeenLastCalledWith('outbox-1', {
      signed_name: 'Switchback',
      signed_name_kind: 'trail',
      contact_ok: true,
    })

    // A real name that is not set yet reads as exactly that, and clears the
    // signature on the report rather than sending a kind with no name.
    await act(async () => {
      fireEvent.click(screen.getByRole('radio', { name: /real name/i }))
    })
    expect(screen.getByTestId('report-signature')).toHaveTextContent(
      'Signed as not set (real name) · thru',
    )
    expect(props.onAmend).toHaveBeenLastCalledWith('outbox-1', {
      signed_name: undefined,
      signed_name_kind: undefined,
      contact_ok: true,
    })

    // Typed and kept on leaving the field: to the preferences through
    // onRealName, and to the report without waiting for them.
    fireEvent.change(screen.getByTestId('reporter-real-name'), {
      target: { value: 'Jane Doe' },
    })
    await act(async () => {
      fireEvent.blur(screen.getByTestId('reporter-real-name'))
    })
    expect(props.onRealName).toHaveBeenCalledWith('Jane Doe')
    expect(props.onAmend).toHaveBeenLastCalledWith('outbox-1', {
      signed_name: 'Jane Doe',
      signed_name_kind: 'real',
      contact_ok: true,
    })
    expect(screen.getByTestId('report-signature')).toHaveTextContent(
      'Signed as Jane Doe (real name) · thru',
    )
  })

  it('carries the signature and the consent onto the next report, and the note only to the one it described', async () => {
    const { props } = await filed()
    fireEvent.change(screen.getByTestId('report-note'), {
      target: { value: 'three trunks' },
    })
    await act(async () => {
      fireEvent.click(screen.getByTestId('reporter-contact-ok'))
    })
    await act(async () => {
      fireEvent.click(screen.getByTestId('report-again'))
    })
    // The note went to the first report on the way out, with the signature
    // and the consent as they stood - a receipt settles whole.
    expect(props.onAmend).toHaveBeenLastCalledWith(
      'outbox-1',
      expect.objectContaining({ note: 'three trunks', contact_ok: true }),
    )

    await act(async () => {
      fireEvent.click(screen.getByTestId('report-tile-trash'))
    })
    const [, note, , extras] = vi.mocked(props.onFile).mock.calls[1] ?? []
    expect(note).toBe('')
    expect(extras).toEqual({
      location: AT_THE_FIX,
      placeWords: '',
      signature: { kind: 'trail', name: 'Switchback' },
      contactOk: true,
    })
  })

  it('keeps a real name typed and then closed over by Escape, which never blurs the field', async () => {
    // Escape runs the window's own close, and removing a focused field fires
    // no blur, so the name would have been shown on the summary and stored
    // nowhere (review of #1571). The receipt settles from its own draft.
    const { props } = await filed()
    await act(async () => {
      fireEvent.click(screen.getByRole('radio', { name: /real name/i }))
    })
    fireEvent.change(screen.getByTestId('reporter-real-name'), {
      target: { value: 'Jane Doe' },
    })
    await act(async () => {
      fireEvent.keyDown(document, { key: 'Escape' })
    })

    expect(props.onRealName).toHaveBeenCalledWith('Jane Doe')
    expect(props.onAmend).toHaveBeenLastCalledWith(
      'outbox-1',
      expect.objectContaining({ signed_name: 'Jane Doe', signed_name_kind: 'real' }),
    )
    expect(props.onClose).toHaveBeenCalledWith(true)
  })

  it('clears the note with an Undo, so it cannot ride onto the next tile', async () => {
    // "Note something else" already cleared it; Undo left it in place, and
    // a note about a blowdown then filed under whichever tile came next
    // (review of #1571).
    const { props } = await filed()
    fireEvent.change(screen.getByTestId('report-note'), {
      target: { value: 'Big oak across the tread' },
    })
    await act(async () => {
      fireEvent.click(screen.getByTestId('report-undo'))
    })
    await act(async () => {
      fireEvent.click(screen.getByTestId('report-tile-flooding'))
    })
    const [, note] = vi.mocked(props.onFile).mock.calls[1] ?? []
    expect(note).toBe('')
  })

  it('offers a real name already in the preferences without asking for it again', async () => {
    await filed({ names: { trail: 'Switchback', real: 'Jane Doe' } })
    await act(async () => {
      fireEvent.click(screen.getByRole('radio', { name: /real name/i }))
    })
    expect(screen.getByTestId('report-signature')).toHaveTextContent(
      'Signed as Jane Doe (real name) · thru',
    )
    expect(screen.getByTestId('reporter-real-name')).toHaveValue('Jane Doe')
  })
})

describe('the refused tap files by itself once the place arrives (#1563)', () => {
  const NIDAY = {
    kind: 'poi' as const,
    poiId: 'p-near',
    name: 'Niday Shelter',
    lat: 37.3,
    lon: -80.3,
    mile: 627.8,
  }

  /** Taps Blow down with nothing to place it at, which opens the sheet. */
  async function refused(overrides: Partial<ReportWindowProps> = {}) {
    const result = setup({ fix: null, places: PLACES, ...overrides })
    await act(async () => {
      fireEvent.click(screen.getByTestId('report-tile-blowdown'))
    })
    expect(result.props.onFile).not.toHaveBeenCalled()
    expect(screen.getByTestId('location-sheet')).toBeInTheDocument()
    return result
  }

  it('files the tapped tile when a row in the sheet places the report, without a second tap', async () => {
    const { props, rerender } = await refused()
    fireEvent.click(screen.getByTestId('location-place-p-near'))
    expect(props.onChooseLocation).toHaveBeenCalledWith(NIDAY)
    // The shell answers with the new place; the tap that was waiting files
    // in the render it arrives in, at that place.
    await act(async () => {
      rerender(<ReportWindow {...props} location={NIDAY} />)
    })
    expect(props.onFile).toHaveBeenCalledTimes(1)
    const [type, , , extras] = vi.mocked(props.onFile).mock.calls[0] ?? []
    expect(type).toBe('blowdown')
    expect(extras?.location).toEqual(NIDAY)
    expect(screen.getByRole('status')).toHaveTextContent(
      'Filed — blow down at Niday Shelter',
    )
  })

  it('files the tapped tile when a spot kept on the map comes back, and not while the window stands aside', async () => {
    const { props, rerender } = await refused({ onPointOnMap: vi.fn() })
    fireEvent.click(screen.getByTestId('location-map'))
    expect(props.onPointOnMap).toHaveBeenCalled()
    await act(async () => {
      rerender(
        <ReportWindow {...props} onPointOnMap={props.onPointOnMap} standingAside />,
      )
    })
    expect(props.onFile).not.toHaveBeenCalled()

    await act(async () => {
      rerender(
        <ReportWindow
          {...props}
          onPointOnMap={props.onPointOnMap}
          location={{ kind: 'point', lat: 37.4, lon: -80.4, mile: 630 }}
        />,
      )
    })
    expect(props.onFile).toHaveBeenCalledTimes(1)
    expect(vi.mocked(props.onFile).mock.calls[0]?.[0]).toBe('blowdown')
    expect(screen.getByRole('status')).toHaveTextContent('Filed — blow down at mi 630.0')
  })

  it('drops the tapped tile when the sheet is dismissed with nothing in it', async () => {
    // The hiker changed their mind. A report filing itself a minute later,
    // once they pick a place for a different reason, would be the wrong
    // kind of surprise.
    const { props, rerender } = await refused()
    fireEvent.click(screen.getByTestId('location-sheet-done'))
    expect(props.onFile).not.toHaveBeenCalled()

    fireEvent.click(screen.getByTestId('report-change-anchor'))
    fireEvent.click(screen.getByTestId('location-place-p-near'))
    await act(async () => {
      rerender(<ReportWindow {...props} location={NIDAY} />)
    })
    expect(props.onFile).not.toHaveBeenCalled()
    expect(screen.getByTestId('report-tile-blowdown')).toBeInTheDocument()
  })

  it('keeps the tapped tile when the sheet is dismissed by Escape with the words typed', async () => {
    const { props } = await refused()
    fireEvent.change(screen.getByTestId('location-words'), {
      target: { value: 'the ford below the gap' },
    })
    await act(async () => {
      fireEvent.keyDown(document, { key: 'Escape' })
    })
    expect(props.onFile).toHaveBeenCalledTimes(1)
    expect(vi.mocked(props.onFile).mock.calls[0]?.[3]?.placeWords).toBe(
      'the ford below the gap',
    )
  })
})
