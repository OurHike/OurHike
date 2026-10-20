/**
 * Org home → Challenges → Finishers: what a club learns about one challenge,
 * which is two counts and a file (#1780, features/CHALLENGES.md).
 *
 * **NO HIKER'S NAME IS EVER DRAWN HERE.** The record is the hiker's, and the
 * club learns a name only when a hiker sends an entry (the guardrail's rule 3,
 * "private by default"). Even then the name reaches the club in the file it
 * downloads and nowhere on this screen: `GET /clubs/{slug}/challenges/{id}/
 * entries` answers CSV only, and this screen hands the text straight to the
 * browser's save without reading a row of it. A list of names on a page is a
 * list somebody screenshots; a file is something the club chose to keep.
 *
 * **THE DOWNLOAD IS NEVER GATED ON ANYTHING BUT THE SERVER.** Value #6 - an
 * organization can always take its data - so the button is there for every
 * challenge, a draft included, and what it cannot do is said beside it
 * rather than by hiding it.
 */

import { useState } from 'react'
import { PageHeader } from '../components'
import { refusalSentence } from '../../lib/api'
import { CHALLENGE_WORDS } from '../../lib/challengeWords'
import type { OrgChallengeRow } from '../orgApi'
import { hikersInLabel } from './Challenges'

/** Hand a CSV to the browser as a download.
 *
 *  The same anchor dance as `lib/accountArchive.ts`'s `downloadArchive` and
 *  `lib/gpsTrace.ts`'s `downloadTrace`, and its third copy: `downloadTrace`
 *  says two callers was not yet a pattern, and three is the point at which a
 *  shared helper is worth somebody's decision rather than this file's. The
 *  revoke is deferred for the reason `downloadArchive` gives - Safari reads
 *  the blob after the click returns, and an early revoke saves an empty file. */
function saveCsv(filename: string, text: string): void {
  // The byte-order mark goes back on. The server writes one so Excel reads
  // "Zoë" as UTF-8, and `Response.text()` strips it on the way in - so the
  // file the club opened read "ZoÃ«" (review, 2026-09-30).
  const bom = '\uFEFF'
  const blob = new Blob([text.startsWith(bom) ? text : bom + text], {
    type: 'text/csv;charset=utf-8',
  })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}

/** `<challenge id>-entries-<YYYY-MM-DD>.csv`, dated because a club exports
 *  more than once and two files with one name overwrite each other. */
export function entriesFilename(challengeId: string, now: Date = new Date()): string {
  return `${challengeId}-entries-${now.toISOString().slice(0, 10)}.csv`
}

export interface ChallengeFinishersProps {
  readonly rows: readonly OrgChallengeRow[]
  /** The list could not be read - said, rather than "none". */
  readonly rowsUnread?: boolean
  /** From `?challenge=`; the first challenge when absent or unknown. */
  readonly challengeId: string | null
  readonly onPick: (challengeId: string) => void
  readonly onBack: (challengeId: string | null) => void
  /** The entries as the server wrote them. Never parsed here. */
  readonly fetchEntries: (challengeId: string) => Promise<string>
  /** Where the text goes. The browser's save unless a test says otherwise. */
  readonly save?: (filename: string, text: string) => void
}

type Download =
  | { state: 'idle' }
  | { state: 'busy' }
  | { state: 'saved'; filename: string }
  | { state: 'failed'; detail: string }

export function ChallengeFinishers({
  rows,
  rowsUnread = false,
  challengeId,
  onPick,
  onBack,
  fetchEntries,
  save = saveCsv,
}: ChallengeFinishersProps) {
  // The challenge asked for, never a different one in its place: a stale
  // `?challenge=` showed the first row's finishers under no warning.
  const row =
    challengeId === null
      ? rows[0]
      : rows.find((candidate) => candidate.challenge_id === challengeId)
  const [download, setDownload] = useState<Download>({ state: 'idle' })

  const header = (
    <PageHeader
      eyebrow="Org home · challenges · finishers"
      title="Finishers"
      sub={
        <>
          Two counts and a file. Who finished is theirs to tell you: an entry a hiker
          sends is in the download, whole, and this page shows only how many.
        </>
      }
      actions={
        <button
          type="button"
          className="org-btn org-btn--ghost org-btn--small"
          onClick={() => onBack(row?.challenge_id ?? null)}
        >
          ← Challenges
        </button>
      }
    />
  )

  if (rowsUnread) {
    return (
      <>
        {header}
        <div className="org-empty">
          <h3>Could not read your challenges</h3>
          <p>
            OurHike did not answer with this organization’s challenges. Reload the page to
            try again.
          </p>
        </div>
      </>
    )
  }

  if (!row && challengeId !== null && rows.length > 0) {
    return (
      <>
        {header}
        <div className="org-empty">
          <h3>That challenge is not here</h3>
          <p>
            This organization has no challenge called {challengeId}. Pick one of its
            challenges from the list.
          </p>
          <div className="org-stack">
            {rows.map((candidate) => (
              <button
                key={candidate.challenge_id}
                type="button"
                className="org-btn org-btn--ghost org-btn--small"
                onClick={() => onPick(candidate.challenge_id)}
              >
                {candidate.name}
              </button>
            ))}
          </div>
        </div>
      </>
    )
  }

  if (!row) {
    return (
      <>
        {header}
        <div className="org-empty">
          <h3>No challenges yet</h3>
          <p>
            Finishers belong to a challenge, and this organization has none. Make one on
            the Challenges page and its entries arrive here.
          </p>
        </div>
      </>
    )
  }

  const take = async () => {
    setDownload({ state: 'busy' })
    try {
      const text = await fetchEntries(row.challenge_id)
      const filename = entriesFilename(row.challenge_id)
      save(filename, text)
      setDownload({ state: 'saved', filename })
    } catch (error) {
      setDownload({
        state: 'failed',
        detail: refusalSentence(error, 'The server did not answer.'),
      })
    }
  }

  const hikersIn = hikersInLabel(row)

  return (
    <>
      {header}

      {rows.length > 1 ? (
        <label className="org-field" style={{ maxWidth: 360 }}>
          <span className="org-field__label">Challenge</span>
          <select
            className="org-select"
            value={row.challenge_id}
            onChange={(event) => {
              setDownload({ state: 'idle' })
              onPick(event.target.value)
            }}
          >
            {rows.map((candidate) => (
              <option key={candidate.challenge_id} value={candidate.challenge_id}>
                {candidate.name}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <h2 className="org-table__name">{row.name}</h2>
      )}

      {row.status === 'draft' ? (
        <div className="org-callout" data-tone="info">
          <span>
            <strong>A draft takes no entries.</strong> Hikers can join it, walk it and{' '}
            {CHALLENGE_WORDS.noun} its places; the finish screen tells them your club has
            not confirmed the list yet, rather than collecting an entry nobody agreed to
            run.
          </span>
        </div>
      ) : null}

      <div className="org-grid org-grid--tiles">
        <div className="org-tile">
          <span className="org-tile__label">Finished</span>
          <span className="org-tile__value">{row.finished.toLocaleString('en-US')}</span>
          <span className="org-tile__meta">A count, with no names.</span>
        </div>
        <div className="org-tile">
          <span className="org-tile__label">Hikers in</span>
          <span className="org-tile__value">{hikersIn}</span>
          <span className="org-tile__meta">
            {row.live === false
              ? 'No phone has it yet. It goes out with the next data refresh after its pull request is merged.'
              : `Below ${row.hikers_in_floor} the number is not shown, so a small challenge cannot describe a few people.`}
          </span>
        </div>
      </div>

      <section className="org-card org-panel">
        <span className="org-eyebrow">Entries sent to you</span>
        <p className="org-panel__note">
          Hikers in is a count only. No names reach you until someone sends an entry.
        </p>
        <p className="org-panel__note">
          An entry carries what the finisher chose to send — a name, and an email or a
          mailing address — and the places they {CHALLENGE_WORDS.past}, each marked as
          found by GPS or {CHALLENGE_WORDS.past} by hand. What a hand{' '}
          {CHALLENGE_WORDS.noun} is worth is yours to decide.
        </p>
        <div className="org-inline">
          <button
            type="button"
            className="org-btn"
            disabled={download.state === 'busy'}
            onClick={() => void take()}
          >
            {download.state === 'busy' ? 'Downloading…' : 'Download entries (CSV)'}
          </button>
          {download.state === 'saved' ? (
            <span className="org-mono">Saved {download.filename}.</span>
          ) : null}
        </div>
        {download.state === 'failed' ? (
          <div className="org-callout" data-tone="warn">
            <span>
              <strong>Nothing was downloaded.</strong> {download.detail}
            </span>
          </div>
        ) : null}
      </section>
    </>
  )
}
