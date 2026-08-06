// Trail / More (WIREFRAMES.md §6). The tab set itself lives in tabs.ts - see
// the note there for why Downloads is no longer one of them.
//
// This bar is also where the OurHike mark lives, because on both layouts the
// bar IS the bottom-left corner of the page. On a desktop it becomes the left
// sidebar (desktop.css) and the mark sits at the foot of it, icon over
// wordmark. On a phone it is a horizontal strip and the mark is the icon
// alone, left of the tabs - the wordmark has nowhere to go there without
// taking width off a thumb target.
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

import { TABS, type TabId } from './tabs'
import logoIcon from '../design-system/assets/logo-icon.svg'

export interface TabBarProps {
  active: TabId
  onSelect: (id: TabId) => void
}

export function TabBar({ active, onSelect }: TabBarProps) {
  return (
    <nav className="tab-bar" aria-label="Main">
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
