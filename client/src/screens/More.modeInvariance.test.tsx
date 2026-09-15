import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { More, type MorePage, type MoreProps } from './More'
import { DEFAULT_PREFERENCES } from '../lib/userPreferences'
import { HIKER_MODE_VALUES, type HikerMode } from '../lib/hikerMode'
import type { DownloadStatus } from './DownloadCard'

// D23: Today, Map and Plan change with the mode switch; MORE DOES NOT.
//
// More is where somebody goes looking for a specific thing. A settings list
// that rearranges itself depending on a switch on another screen is a list
// you have to re-learn every time - and the way into volunteering cannot be
// behind the mode you are already in.
//
// THIS FILE EXISTS BECAUSE THE PROPERTY ALREADY HOLDS (#1437). `destinations`
// takes no mode input and the shell hands down `volunteerScreen`
// unconditionally, so there was nothing to fix - only a property holding by
// accident, one `mode === 'volunteer' &&` away from not holding, with nothing
// that would fail on the day somebody wrote it.
//
// THE ONE DIFFERENCE THIS FILE ALLOWS, and why it is not a hole in the rule:
// the You row's summary line names the current mode ("Switchback · day
// hiking · signed in"), because More -> You is where the mode switch itself
// lives (screens/Settings.tsx's YouSettings). A control showing its own
// current value is not a list that rearranges itself. D23's acceptance
// sentence - "the only difference anywhere on screen is the mode word on the
// tab bar" - is stricter than that, and the exception is asserted here rather
// than waived, so a SECOND row learning to read the mode fails this suite.

const NOT_DOWNLOADED: DownloadStatus = { state: 'not-downloaded' }

const PROPS = {
  page: 'home' as MorePage,
  onNavigate: vi.fn(),
  account: null as { email: string } | null,
  reporterType: 'thru' as const,
  onSignIn: vi.fn(),
  onSignOut: vi.fn(),
  preferences: DEFAULT_PREFERENCES,
  onChange: vi.fn(),
  lastSyncedAt: null,
  onSync: vi.fn(),
  onExport: vi.fn(),
  onStartReport: vi.fn(),
  onChangeMode: vi.fn(),
  queuedReportCount: 0,
  hikingStatus: NOT_DOWNLOADED,
} satisfies Partial<MoreProps>

/** The three mode phrases screens/More.tsx's MODE_PHRASE prints, in either
 *  case: `summaryLine` raises the first letter when the mode word leads the
 *  line, which it does for a hiker who has set no trail name. Case-insensitive
 *  rather than three literals, so the raised form is not a second thing to
 *  keep in step. */
const MODE_WORD = /day hiking|on a long hike|volunteering/i

/** What the home screen offers, as a hiker reads it: every row's title and
 *  sub-line, in the order they are drawn. The whole comparison, so a row
 *  added, dropped, reworded or moved for one mode fails rather than three
 *  narrower assertions each missing a different way to break the rule. */
function homeRows(container: HTMLElement): Array<[string, string]> {
  return Array.from(container.querySelectorAll('.more__row')).map((row) => [
    row.querySelector('.more__row-title')?.textContent ?? '',
    row.querySelector('.more__row-sub')?.textContent ?? '',
  ])
}

function renderHome(mode: HikerMode) {
  return render(<More {...PROPS} mode={mode} />).container
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('More takes no mode input', () => {
  it('draws the same rows, in the same order, in all three modes', () => {
    // Read against day hiking rather than a literal list: this file is about
    // the three renders AGREEING, and screens/More.test.tsx already owns what
    // the five rows say. A literal here would be a second home for that.
    const expected = homeRows(renderHome('day')).map(([title, sub]) => [
      title,
      // The one sanctioned difference, replaced on both sides rather than
      // skipped - see the header. Everything else in the sub-line still has
      // to match, so "Not signed in" drifting in one mode still fails.
      title === 'You' ? sub.replace(MODE_WORD, '·mode·') : sub,
    ])
    cleanup()

    for (const mode of HIKER_MODE_VALUES) {
      const actual = homeRows(renderHome(mode)).map(([title, sub]) => [
        title,
        title === 'You' ? sub.replace(MODE_WORD, '·mode·') : sub,
      ])
      expect(actual, `More's rows under ${mode} mode`).toEqual(expected)
      cleanup()
    }
  })

  it('keeps the way into volunteering in every mode', () => {
    // The row D23 names specifically: "the way in cannot be behind the mode
    // you are already in". A hiker in day-hike mode who wants to hand
    // something back has to be able to find it from here.
    for (const mode of HIKER_MODE_VALUES) {
      renderHome(mode)
      expect(
        screen.getByRole('button', { name: /^Volunteer & report/ }),
        `the volunteering door under ${mode} mode`,
      ).toBeInTheDocument()
      cleanup()
    }
  })

  it('names the mode on the You row, and nowhere else', () => {
    // The exception, pinned. Volunteer mode's word is "volunteering", and it
    // appears once: on the row that opens the screen holding the switch.
    renderHome('volunteer')

    const naming = Array.from(document.querySelectorAll('.more__row')).filter((row) =>
      /volunteering/i.test(row.textContent ?? ''),
    )
    expect(naming).toHaveLength(1)
    expect(naming[0].querySelector('.more__row-title')?.textContent).toBe('You')
  })

  it('draws the same group headings on every page, in all three modes', () => {
    // The rows are one half of "does not rearrange itself"; the pages behind
    // them are the other. Headings rather than contents, because the You page
    // legitimately differs - it holds the switch, and the switch shows which
    // mode is pressed.
    const pages: MorePage[] = ['you', 'map', 'safety', 'volunteer', 'sources']

    for (const page of pages) {
      const headings = HIKER_MODE_VALUES.map((mode) => {
        const { container } = render(<More {...PROPS} page={page} mode={mode} />)
        const found = Array.from(container.querySelectorAll('.settings__heading')).map(
          (heading) => heading.textContent,
        )
        cleanup()
        return found
      })

      expect(headings[1], `More's "${page}" page under long-hike mode`).toEqual(
        headings[0],
      )
      expect(headings[2], `More's "${page}" page under volunteer mode`).toEqual(
        headings[0],
      )
    }
  })
})
