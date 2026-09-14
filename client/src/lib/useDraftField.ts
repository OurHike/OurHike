// A text field's own copy of a stored value, committed when the hiker is
// done with it rather than on every keystroke (#1374 review).
//
// The saved card's name and a walked record's note are written through a
// read-modify-write of the whole day-hike store (App's handleSetDayHikeName:
// load, replace the row, save). Committing per keystroke put two of those in
// flight at once, both reading the same stored name, so the second write
// lost the first's letter - and the controlled input, bound to the store,
// snapped back between them. One write per edit, on blur, is what the store
// can take; the field holds the letters in the meantime.

import { useCallback, useEffect, useRef, useState } from 'react'

export function useDraftField(
  value: string,
  commit: (next: string) => void,
): { draft: string; setDraft: (next: string) => void; flush: () => void } {
  const [draft, setDraft] = useState(value)
  const committed = useRef(value)
  const draftRef = useRef(draft)
  draftRef.current = draft
  const commitRef = useRef(commit)
  commitRef.current = commit

  // A new stored value - another record in the same card, or an edit that
  // landed from another device - replaces what was typed.
  useEffect(() => {
    setDraft(value)
    committed.current = value
  }, [value])

  const flush = useCallback(() => {
    if (draftRef.current === committed.current) return
    committed.current = draftRef.current
    commitRef.current(draftRef.current)
  }, [])

  return { draft, setDraft, flush }
}
