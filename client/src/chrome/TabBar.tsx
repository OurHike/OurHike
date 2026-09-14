// Trail / Plan / Settings (WIREFRAMES.md §6, features/MORE_TAB.md). The tab
// set itself lives in tabs.ts - see the note there for why Downloads is no
// longer one of them, and MORE_TAB.md for why the third tab reads "Settings"
// rather than "More".
//
// This bar is also where the OurHike mark lives on a desktop, because there
// the bar IS the bottom-left corner of the page: it becomes the left sidebar
// (desktop.css) and the mark sits at the foot of it, icon over wordmark. On a
// phone the bar is a horizontal strip of thumb targets and carries no mark at
// all since 2026-09-10 (the room audit for #1374): the left end of the row is
// spent on the mode chip below, which says something the tabs do not, and the
// 24px icon that sat there was 32px of the tabs' width spent on branding. The
// mark is kept in the markup for the sidebar; chrome.css decides which layout
// draws it.
//
// The mark rides here rather than on the map itself because the map is the
// product, and a watermark over it costs terrain a hiker may be reading. In the
// bar it costs no map at all.
//
// The icon is the design system's standalone asset rather than <Logo />, for
// two reasons. Its size differs per layout (24px against 64px) and an <img> is
// sized by CSS, where <Logo />'s inline width, height and border-radius would
// have to be fought with `!important` at one of the two. And <Logo /> pairs the
// wordmark with the icon at a fixed 30/96 ratio, which at a 64px icon caps the
// type at 20px - too small for the sidebar, and the horizontal lockup at a size
// that would fix it is wider than the sidebar itself. So the sidebar stacks the
// two, with the wordmark mirroring Logo.jsx's own type styling (see
// .tab-bar__brand-wordmark in chrome.css) so they cannot drift into looking
// like different brands on different screens.
//
// Worth being straight about the cost: stacked, this is no longer the design
// system's "4a - Dual-Tone Horizontal Lockup", whose proportions that project
// calls final.
//
// The tabs sit in their own element rather than directly under the <nav>. A
// `role="tablist"` is required to own tabs and nothing else, so hanging the
// mark off it would make the brand one more member of the set - which is
// exactly what a screen reader would then announce.

import type { ReactNode } from 'react'
import { TABS, type TabId } from './tabs'
import { HIKER_MODE_LABELS, type HikerMode } from '../lib/hikerMode'
import { ModeIcon } from './ModeIcon'
import logoIcon from '../design-system/assets/logo-icon.svg'

export interface TabBarProps {
  active: TabId
  onSelect: (id: TabId) => void
  /**
   * The sidebar's mode block (#1054): the "today I'm…" control, rendered
   * between the tabs and the brand mark. The shell passes it only above the
   * breakpoint - the phone's bar is a strip of thumb targets with no room
   * for a second control, and the phone already carries the switch on the
   * Today header. A slot rather than this bar owning ModeSwitch, so the bar
   * stays ignorant of hiker modes and every home renders the one component
   * (chrome/ModeSwitch.tsx).
   */
  modeSwitch?: ReactNode
  /**
   * The hike a hiker is on, as a control (#1344), under the mode block.
   *
   * ITS OWN SLOT RATHER THAN PART OF `modeSwitch`, because the two answer
   * different questions and the eyebrow above only asks one. "Today I'm ▸
   * Long hike" is a mode; "Springer → Katahdin" is which hike, and reading
   * the second as an answer to the first would make the hike look like a
   * fourth mode segment.
   *
   * The sidebar is on every screen, which is the whole point: before this,
   * `Switch hike ›` existed on the Plan band and nowhere else. Passed only
   * above the breakpoint, for `modeSwitch`'s own reason - a phone's bar is
   * three thumb targets - and the phone carries the same door on Today's
   * header instead.
   */
  hikeSwitch?: ReactNode
  /**
   * Which of the three modes the hiker is in, read out as the left chip of
   * the tab row (#1373, review rule R11): "Four tabs and the mode, on every
   * screen … a read-out that opens the one control, never a second switch."
   * A chip in the row rather than a row of its own since 2026-09-10: the
   * room audit at 375×667 measured the bar at 105px - three rows, the brand
   * mark alone on the first - against 45px with the chip in the row.
   *
   * A READ-OUT, NOT A SWITCH. The phone's bar is a strip of thumb targets and
   * App.test.tsx pins that no radiogroup lives in it; this row is one button
   * that opens the one ModeSwitch (on Today's header) rather than a copy of
   * it. The shell passes it on the phone only - the desktop sidebar carries
   * the switch itself through `modeSwitch`, and a read-out under a switch
   * would answer the same question twice. First run passes nothing: the
   * shell does not exist yet.
   */
  mode?: HikerMode
  /** Open the one mode control. Without it the row still reads, as text. */
  onOpenMode?: () => void
}

export function TabBar({
  active,
  onSelect,
  modeSwitch,
  hikeSwitch,
  mode,
  onOpenMode,
}: TabBarProps) {
  const readout =
    mode === undefined ? null : (
      <>
        <ModeIcon mode={mode} size={18} className="tab-bar__mode-icon" />
        <span className="tab-bar__mode-word">{HIKER_MODE_LABELS[mode]}</span>
        {onOpenMode !== undefined && (
          <>
            <span className="tab-bar__mode-caret" aria-hidden="true">
              ▾
            </span>
          </>
        )}
      </>
    )

  return (
    <nav className="tab-bar" aria-label="Main">
      {readout !== null &&
        (onOpenMode === undefined ? (
          <div className="tab-bar__readout">
            <span className="visually-hidden">Today I’m </span>
            {readout}
          </div>
        ) : (
          <button
            type="button"
            className="tab-bar__readout tab-bar__readout--opens"
            onClick={onOpenMode}
            aria-label={`Today I’m ${HIKER_MODE_LABELS[mode!].toLowerCase()}. Switch mode`}
          >
            {readout}
          </button>
        ))}
      <div className="tab-bar__tabs" role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            className="tab-bar__tab"
            aria-selected={tab.id === active}
            // Fires even when already active, so the screen can scroll to top -
            // the standard tab-bar affordance people already expect.
            onClick={() => onSelect(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Above the brand mark, so the tab list's flex growth carries both to
          the foot of the sidebar together. The eyebrow is aria-hidden because
          the control inside already names itself "Today I'm" - a visible
          label AND an aria-label would announce the question twice. */}
      {modeSwitch !== undefined && (
        <div className="tab-bar__mode">
          <p className="tab-bar__mode-label" aria-hidden="true">
            Today I’m
          </p>
          {modeSwitch}
        </div>
      )}

      {/* ITS OWN BLOCK, WITH ITS OWN EYEBROW, and the first attempt is why.
          Dropped straight in under the mode segments it read as a FOURTH
          segment - same column, same width, same rounded outline - which is
          the exact confusion the slot was split to avoid, arrived at anyway
          because splitting the prop did nothing about the picture. The rule
          above it and the eyebrow are what make it a different question.

          Same aria-hidden reason as the mode block's: the control inside
          names itself, and a visible label plus an accessible one announces
          it twice. */}
      {hikeSwitch !== undefined && (
        <div className="tab-bar__hike-block">
          <p className="tab-bar__mode-label" aria-hidden="true">
            On the hike
          </p>
          {hikeSwitch}
        </div>
      )}

      {/* Rendered on every screen, not only the map: the sidebar is one shared
          piece of chrome, and a mark that appeared under Trail and vanished
          under More would read as a bug rather than as branding.

          Hidden from assistive tech as a whole. `iconOnly` gives the icon its
          own "OurHike" label, so left alone this block announces the name
          twice in a row - and the one thing a screen reader gains from a
          footer brand mark is nothing it can act on. The app names itself in
          the document title and at onboarding. */}
      <div className="tab-bar__brand" aria-hidden="true">
        <img className="tab-bar__brand-icon" src={logoIcon} alt="" />
        <span className="tab-bar__brand-wordmark">OurHike</span>
      </div>
    </nav>
  )
}
