// Small pieces every challenge surface shares (#1780): the diamond, the draft
// label, the finish bar, the Tag it pill, an organization's mark, and the one
// way a challenge row is worded. One copy of each, so the list, a challenge's
// own page, the place card, Today's camp card and Plan's card cannot drift
// into five spellings of the same thing.

import { CHALLENGE_WORDS } from '../lib/challengeWords'
import { draftLabel, type Challenge } from '../lib/challenges'
import '../screens/challenges.css'

/** The challenge place glyph: a blaze-yellow diamond, hollow until done. */
export function Diamond({ done, big = false }: { done: boolean; big?: boolean }) {
  const classes = ['challenge-diamond']
  if (done) classes.push('challenge-diamond--done')
  if (big) classes.push('challenge-diamond--big')
  return <span className={classes.join(' ')} aria-hidden="true" />
}

/** The maintainer's condition for publishing a draft at all (poll,
 *  2026-09-30): wherever the challenge is named, so is this. */
export function DraftLabel({ challenge }: { challenge: Challenge }) {
  const label = draftLabel(challenge)
  return label === null ? null : <span className="challenge-draft">{label}</span>
}

/** The finish bar - drawn only where a finish line exists, and only on the
 *  list and the challenge's own page. Presentational: the count beside it is
 *  the text a screen reader hears. */
export function FinishBar({ tagged, finish }: { tagged: number; finish: number }) {
  const share = Math.max(0, Math.min(1, finish === 0 ? 0 : tagged / finish))
  return (
    <div className="challenge-bar" aria-hidden="true">
      <div
        className="challenge-bar__fill"
        style={{ width: `${Math.round(share * 100)}%` }}
      />
    </div>
  )
}

/** "Tag it" / "Tagged" - toggles at once (optimistic); the outbox handles
 *  delivery. */
export function TagPill({
  tagged,
  onPress,
  disabled = false,
  label,
}: {
  tagged: boolean
  onPress: () => void
  disabled?: boolean
  /** The accessible name, which must say WHICH item - a list of ten
   *  identical "Tag it" buttons is a list nobody can use by ear. */
  label: string
}) {
  return (
    <button
      type="button"
      className="challenge-tag"
      aria-pressed={tagged}
      aria-label={label}
      disabled={disabled}
      onClick={onPress}
    >
      {tagged ? CHALLENGE_WORDS.done : CHALLENGE_WORDS.act}
    </button>
  )
}

/** An organization's mark: its short name on a tile until the org uploads
 *  art. */
export function OrgMark({ challenge }: { challenge: Challenge }) {
  return (
    <span className="challenge-org" aria-hidden="true">
      {challenge.orgShort.slice(0, 5)}
    </span>
  )
}
