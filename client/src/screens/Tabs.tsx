// One strip of tabs over one panel, for choosing between things that are
// alternatives rather than a list.
//
// Built for the background sheets (lib/packages.ts): the hiking sheet, the
// USGS raster, and whatever the pipeline publishes next. Stacked cards were
// right while there was one of them and nearly right with two; at three the
// window becomes a scroll through downloads a hiker is mostly not choosing,
// and the thing they came to compare - what each map costs - is never on
// screen at the same time as the thing it is being compared against.
//
// The same strip is used by first run (screens/Onboarding.tsx) and by the
// download window (screens/Downloads.tsx), because those two screens ask the
// same question and used to ask it in two different shapes.
//
// ONE PANEL, RENDERED, NOT THREE HIDDEN WITH CSS.
//
// Only the selected tab's content exists in the tree. Hiding the others with
// `display: none` would leave their radios, buttons and progress bars
// reachable by a screen reader in some browsers and by tab order in others,
// and would keep a `role="status"` warning about a download nobody is looking
// at mounted and announced.
//
// Automatic activation - arrow keys move the selection AND the panel - which
// is the WAI-ARIA pattern's recommendation wherever showing a panel is cheap.
// It is cheap here: every panel is already-computed local state.

import { useRef, type KeyboardEvent, type ReactNode } from 'react'
import './tabs.css'

export interface TabItem {
  id: string
  label: string
}

export interface TabsProps {
  /** What this set of tabs is choosing between, for a screen reader. */
  label: string
  tabs: readonly TabItem[]
  activeId: string
  onSelect: (id: string) => void
  /** Distinguishes these tabs' element ids from another strip's on the same
   *  page - the panel is wired to its tab by id, so two strips sharing one
   *  would label each other's panels. */
  idPrefix: string
  /** The selected tab's panel. */
  children: ReactNode
}

export function Tabs({ label, tabs, activeId, onSelect, idPrefix, children }: TabsProps) {
  const strip = useRef<HTMLDivElement>(null)

  const tabId = (id: string) => `${idPrefix}-tab-${id}`
  const panelId = (id: string) => `${idPrefix}-panel-${id}`

  /**
   * Arrow keys move between tabs, Home and End to the ends.
   *
   * The moved-to tab is focused as well as selected: with a roving tabindex
   * the tab left behind is no longer focusable, so leaving focus where it was
   * would drop it to the document body mid-press.
   */
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const current = tabs.findIndex((tab) => tab.id === activeId)
    if (current === -1) return

    const next =
      event.key === 'ArrowRight'
        ? (current + 1) % tabs.length
        : event.key === 'ArrowLeft'
          ? (current - 1 + tabs.length) % tabs.length
          : event.key === 'Home'
            ? 0
            : event.key === 'End'
              ? tabs.length - 1
              : null

    if (next === null) return
    event.preventDefault()
    onSelect(tabs[next].id)
    strip.current?.querySelectorAll('button')[next]?.focus()
  }

  return (
    <div className="tabs">
      <div
        ref={strip}
        className="tabs__strip"
        role="tablist"
        aria-label={label}
        onKeyDown={onKeyDown}
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={tabId(tab.id)}
            className="tabs__tab"
            aria-selected={tab.id === activeId}
            aria-controls={panelId(tab.id)}
            // The roving tabstop: one tab in the page's tab order, arrows for
            // the rest. Tabbing through a strip of them and then into the
            // panel is what the pattern exists to avoid.
            tabIndex={tab.id === activeId ? 0 : -1}
            onClick={() => onSelect(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div
        className="tabs__panel"
        role="tabpanel"
        id={panelId(activeId)}
        aria-labelledby={tabId(activeId)}
        // Focusable because the panel is not guaranteed to start with
        // something focusable - a sheet already on the phone is a paragraph
        // and a delete button - and a panel a keyboard cannot reach is a
        // panel a keyboard cannot read.
        tabIndex={0}
      >
        {children}
      </div>
    </div>
  )
}
