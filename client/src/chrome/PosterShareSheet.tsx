// "Share your summer" - the share poster, made on the phone (#1965, frame
// features/design/blaze-card/Poster.dc.html; the brief's Decisions).
//
// THE MAP BY DEFAULT, WHEN THE PHONE HOLDS ONE (the maintainer, by poll on
// 2026-11-04, from the two posters as built - overruling the brief's
// "strip default, map opt-in"). The map card says what it does, "This shows
// where you've been.", so the hiker sees that before they share; the states
// poster is the other card, one tap away, for a hiker who would rather not
// show where they walk. With no map on the phone the sheet opens on the
// states poster and the map card says why it cannot be chosen.
//
// MADE ON DEMAND, WITH A VISIBLE STATE (the brief's "Second look"): the
// poster is drawn when the sheet opens and again when the choice changes,
// and "Making your poster…" says so meanwhile. Nothing is uploaded: the PNG
// goes to the phone's own share sheet, or is saved, and nowhere else.

import { useEffect, useRef, useState } from 'react'
import type { ChallengeMap } from '../lib/challengeMap'
import type { Challenge } from '../lib/challenges'
import type { ChallengeTag } from '../lib/challengeProgress'
import { seasonWord, type StateOfMile } from '../lib/seasonStrip'
import type { UnitSystem } from '../lib/units'
import type { MileRange } from '../lib/walkedMiles'
import '../screens/challenges.css'

export interface PosterShareSheetProps {
  challenge: Challenge
  tags: readonly ChallengeTag[]
  today: string
  stateOf: StateOfMile
  walked: readonly MileRange[]
  units: UnitSystem
  /** The map, when the phone holds one; without it the map card is off. */
  map: ChallengeMap | null
  onClose: () => void
  /** For tests: the phone's share sheet, when it takes files. */
  share?: (file: File) => Promise<void>
  canShareFiles?: (file: File) => boolean
}

type Made =
  | { kind: 'making' }
  | { kind: 'ready'; url: string; file: File }
  | { kind: 'failed'; why: string }

function defaultCanShare(file: File): boolean {
  return (
    typeof navigator !== 'undefined' &&
    typeof navigator.canShare === 'function' &&
    navigator.canShare({ files: [file] })
  )
}

export function PosterShareSheet(props: PosterShareSheetProps) {
  const { challenge, onClose } = props
  const [withMap, setWithMap] = useState(props.map !== null)
  const [made, setMade] = useState<Made>({ kind: 'making' })
  const season = seasonWord(challenge.window)
  // Which drawing is the latest asked for, so a slow one finishing after a
  // newer choice never replaces it; and the image URL to give back.
  const request = useRef(0)
  const shown = useRef<string | null>(null)

  const draw = async (map: boolean): Promise<void> => {
    const ticket = ++request.current
    try {
      const poster = await import('../lib/challengePoster')
      const fontCss = await poster.posterFontCss().catch(() => '')
      const svg = poster.posterSvg({
        challenge: props.challenge,
        tags: props.tags,
        today: props.today,
        stateOf: props.stateOf,
        walked: props.walked,
        units: props.units,
        map: map ? props.map : null,
        fontCss,
      })
      const blob = await poster.rasterise(svg)
      if (ticket !== request.current) return
      if (shown.current !== null) URL.revokeObjectURL(shown.current)
      const url = URL.createObjectURL(blob)
      shown.current = url
      const file = new File([blob], `${challenge.id}-${season}.png`, {
        type: 'image/png',
      })
      setMade({ kind: 'ready', url, file })
    } catch (error: unknown) {
      if (ticket === request.current) {
        setMade({
          kind: 'failed',
          why: error instanceof Error ? error.message : 'The poster could not be made.',
        })
      }
    }
  }

  // The first drawing, the default above, as the sheet opens; every later
  // one comes from the hiker's choice below. The record does not change
  // while the sheet is open.
  const first = useRef(() => draw(props.map !== null))
  useEffect(() => {
    void first.current()
    return () => {
      request.current += 1
      if (shown.current !== null) URL.revokeObjectURL(shown.current)
    }
  }, [])

  const choose = (map: boolean) => {
    if (map === withMap) return
    setWithMap(map)
    setMade({ kind: 'making' })
    void draw(map)
  }

  const canShare = props.canShareFiles ?? defaultCanShare
  const share = props.share ?? ((file: File) => navigator.share({ files: [file] }))

  const option = (map: boolean, title: string, sub: string, disabled = false) => (
    <div className={`where-option${withMap === map ? ' where-option--chosen' : ''}`}>
      <button
        type="button"
        className="where-option__press"
        aria-pressed={withMap === map}
        disabled={disabled}
        onClick={() => choose(map)}
      >
        <span className="where-option__title">{title}</span>
        <span className="where-option__sub">{sub}</span>
      </button>
    </div>
  )

  return (
    <div
      className="challenge-sheet where-sheet poster-sheet"
      role="dialog"
      aria-modal="true"
      aria-labelledby="poster-heading"
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          event.stopPropagation()
          onClose()
        }
      }}
    >
      <header className="where-sheet__head">
        <div className="where-sheet__top">
          <button
            type="button"
            className="challenge-link where-sheet__back"
            onClick={onClose}
          >
            ‹ Back
          </button>
        </div>
        <h2 className="where-sheet__heading" id="poster-heading">
          Share your {season}
        </h2>
      </header>
      <div className="poster-sheet__preview" aria-live="polite">
        {made.kind === 'making' && (
          <p className="poster-sheet__state">Making your poster…</p>
        )}
        {made.kind === 'failed' && <p className="poster-sheet__state">{made.why}</p>}
        {made.kind === 'ready' && (
          <img
            className="poster-sheet__image"
            src={made.url}
            alt={
              withMap
                ? 'Your poster: the card, the map and the states'
                : 'Your poster: the card and the states'
            }
          />
        )}
      </div>
      <div className="where-sheet__options">
        {option(
          true,
          'The map',
          props.map === null
            ? 'No map on this phone yet.'
            : 'This shows where you’ve been.',
          props.map === null,
        )}
        {option(
          false,
          'The states',
          'The card and a strip of the fourteen states. Nothing says where on the trail.',
        )}
      </div>
      <div className="poster-sheet__actions">
        {made.kind === 'ready' && canShare(made.file) ? (
          <button
            type="button"
            className="challenge-button"
            onClick={() => void share(made.file).catch(() => {})}
          >
            Share
          </button>
        ) : (
          made.kind === 'ready' && (
            <a className="challenge-button" href={made.url} download={made.file.name}>
              Save the image
            </a>
          )
        )}
        <p className="challenges__note">
          Made on this phone. Nothing is sent until you share it.
        </p>
      </div>
    </div>
  )
}
