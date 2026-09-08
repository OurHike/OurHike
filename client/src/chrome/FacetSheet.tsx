// One facet at a time (#1284): the bottom sheet a facet chip opens.
//
// chrome.css's .route-entrance treatment - the brand's top rule, not the
// danger one, because nothing about a filter changes what a hiker does next
// - docked over the Find screen with a scrim, holding one facet's options and
// nothing else. Two facets on one sheet would be a form; this is a question.
//
// COUNTS ARE WHAT MAKE IT HONEST. Every option says how many hikes it would
// leave, and the primary button says the number it is about to show. The
// numbers come from lib/suggestedHikes.ts's `facetCounts`, taken over a draft
// of the facets the caller keeps: picking an option changes the draft, "Show
// N hikes" commits it, and closing the sheet discards it - so the chip row
// behind the scrim never changes under a hiker who is still deciding.
//
// Without an `onShow` it is a picker: a tap applies itself and the caller
// closes it. The results screen's sort control is that - a sort has no count
// to print and nothing to clear.

import { useEffect, useRef } from 'react'
import { Button } from '../design-system/components'
import { HikeFinderIcon } from './HikeFinderIcon'

export interface FacetSheetOption {
  id: string
  label: string
  /** A second line under the label - the publishers under an author kind. */
  note?: string
  /** How many hikes picking this would leave. Absent on a picker. */
  count?: number
  selected: boolean
}

export interface FacetSheetProps {
  title: string
  /** The right-aligned qualifier beside the title - "at your pace". */
  aside?: string
  options: readonly FacetSheetOption[]
  onToggle: (id: string) => void
  caveat?: string
  /** What the primary button will show. With `onShow`, the footer renders. */
  showCount?: number
  onClear?: () => void
  onShow?: () => void
  onClose: () => void
}

export function FacetSheet({
  title,
  aside,
  options,
  onToggle,
  caveat,
  showCount = 0,
  onClear,
  onShow,
  onClose,
}: FacetSheetProps) {
  const sheet = useRef<HTMLDivElement>(null)

  // Focus lands on the dialog so a keyboard or a screen reader is inside
  // it, and Escape is the same way out the scrim is.
  useEffect(() => {
    sheet.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <>
      <div className="facet-sheet__scrim" data-testid="facet-scrim" onClick={onClose} />
      <div
        ref={sheet}
        className="facet-sheet"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
      >
        <div className="facet-sheet__head">
          <h2 className="facet-sheet__title">{title}</h2>
          {aside !== undefined && <span className="facet-sheet__aside">{aside}</span>}
        </div>

        <div className="facet-sheet__options">
          {options.map((option) => (
            <button
              key={option.id}
              type="button"
              className={
                option.selected
                  ? 'facet-sheet__option facet-sheet__option--selected'
                  : 'facet-sheet__option'
              }
              aria-pressed={option.selected}
              onClick={() => onToggle(option.id)}
            >
              <span className="facet-sheet__option-text">
                <span>{option.label}</span>
                {option.note !== undefined && (
                  <span className="facet-sheet__option-note">{option.note}</span>
                )}
              </span>
              {(option.count !== undefined || option.selected) && (
                <span className="facet-sheet__count">
                  {option.count !== undefined && (
                    <span data-testid={`facet-count-${option.id}`}>{option.count}</span>
                  )}
                  {option.selected && (
                    <HikeFinderIcon
                      name="check"
                      strokeWidth={2}
                      className="facet-sheet__check"
                    />
                  )}
                </span>
              )}
            </button>
          ))}
        </div>

        {caveat !== undefined && <p className="facet-sheet__caveat">{caveat}</p>}

        {onShow !== undefined && (
          // Two equal widths through the Button's `style`, which Button.jsx
          // spreads last - the same thing .today__crew relies on.
          <div className="facet-sheet__footer">
            <Button
              variant="outline"
              size="s"
              style={{ flex: 1, justifyContent: 'center' }}
              onClick={onClear}
            >
              Clear
            </Button>
            <Button
              variant="primary"
              size="s"
              style={{ flex: 1, justifyContent: 'center' }}
              onClick={onShow}
            >
              {showCount === 1 ? 'Show 1 hike' : `Show ${showCount} hikes`}
            </Button>
          </div>
        )}
      </div>
    </>
  )
}
