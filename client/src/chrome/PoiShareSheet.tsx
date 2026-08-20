// The moment a private photo becomes a public one (#577), said in plain
// words before it happens. The copy is the maintainer-adopted mockup's
// ("Sharing a Photo", 2026-08-19), sentence for sentence where the facts
// allow: three disclosures, then the one split that must not be blurred -
// what OurHike can always undo against what nobody can.
//
// A bottom sheet over a live map, no scrim - the mockup's own annotation:
// "The map stays visible and live. No sheet in this app has a scrim." It
// renders through a portal because its natural parent is the waypoint
// card, and the card is a transformed, overflow-hidden box a
// position:fixed child cannot escape (a transform makes the card the
// containing block for fixed descendants). The portal is the smallest
// honest exit; the sheet still behaves as the card's own dialog.
//
// What this sheet never becomes (#577): no "share all", no default-on
// toggle, no count of anything. It appears when the hiker taps Share on
// their own photo, and declining is one tap that is never mentioned again.

import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { loadPreferences } from '../lib/preferences'
import { COOLING_OFF_HOURS } from '../lib/photoShare'

export interface PoiShareSheetProps {
  /** Object URL of the stored 640px rendering - the exact bytes a share
   *  sends, previewed so "what they get" is the thing on screen. */
  photoUrl: string
  /** Measured size of those bytes. */
  photoBytes: number
  /** The month the card prints for this photo, e.g. "Jun 2026". */
  photoMonth: string
  poiName: string
  onShare: () => void
  onClose: () => void
}

interface SheetIdentity {
  trailName: string | null
  anonymityDays: number
}

export function PoiShareSheet({
  photoUrl,
  photoBytes,
  photoMonth,
  poiName,
  onShare,
  onClose,
}: PoiShareSheetProps) {
  // The two identity facts the sheet's sentences turn on, read from the
  // device's own preferences: who the credit names, and whether the
  // anonymity window will withhold it for a while. Null until loaded -
  // the sheet renders its facts only once it can state them truthfully.
  const [identity, setIdentity] = useState<SheetIdentity | null>(null)

  useEffect(() => {
    let cancelled = false
    loadPreferences()
      .then((preferences) => {
        if (cancelled) return
        setIdentity({
          trailName:
            preferences.trail_name !== null && preferences.trail_name.trim() !== ''
              ? preferences.trail_name
              : null,
          anonymityDays: preferences.anonymity_window_days,
        })
      })
      .catch(() => {
        if (!cancelled) setIdentity({ trailName: null, anonymityDays: 0 })
      })
    return () => {
      cancelled = true
    }
  }, [])

  const sheet = (
    <div className="share-sheet" role="dialog" aria-label="Share this photo">
      <div className="share-sheet__head">
        <h2 className="share-sheet__title">Share this photo</h2>
        <button type="button" className="share-sheet__close" onClick={onClose}>
          <span className="visually-hidden">Close without sharing</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      <div className="share-sheet__subject">
        <img className="share-sheet__preview" src={photoUrl} alt="" />
        <div className="share-sheet__facts">
          <p className="share-sheet__poi">{poiName}</p>
          <p className="share-sheet__meta">
            {photoMonth} · 640 px · {Math.max(1, Math.round(photoBytes / 1024))} KB
          </p>
        </div>
      </div>

      {identity === null ? null : identity.trailName === null ? (
        // No trail name means nothing to credit the photo to, and the
        // server would refuse the share for exactly that reason. Said
        // here, before anything queues, rather than discovered as a
        // stuck outbox item days later.
        <p className="share-sheet__block" data-testid="share-sheet-no-name">
          Sharing needs a trail name to credit the photo to, and this phone has not set
          one. Set a trail name under Report settings first — your real name is never
          shown either way.
        </p>
      ) : (
        <>
          <div className="share-sheet__disclosures">
            <div className="share-sheet__disclosure">
              <h3>Who sees it</h3>
              <p>
                Every hiker who opens {poiName}. You are credited as{' '}
                <strong>{identity.trailName}</strong> — OurHike never shows anyone your
                real name.
                {identity.anonymityDays > 0 &&
                  ` For ${identity.anonymityDays} more ${
                    identity.anonymityDays === 1 ? 'day' : 'days'
                  } even ${identity.trailName} is withheld, along with the exact date, the same as on your reports.`}
              </p>
            </div>
            <div className="share-sheet__disclosure">
              <h3>What they get</h3>
              <p>
                The 640-pixel copy above, not your photograph. Nobody can download the
                original — OurHike never had it.
              </p>
            </div>
            <div className="share-sheet__disclosure">
              <h3>What leaves this phone</h3>
              <p>
                The picture and the month. Where you were standing is stripped out here,
                before it is sent — not on a server afterwards.
              </p>
            </div>
          </div>

          <div className="share-sheet__promises">
            <h3>Two different promises</h3>
            <p>
              <strong>OurHike stops showing it whenever you ask.</strong> That one is
              kept.
            </p>
            <p>
              <strong>The licence cannot be taken back.</strong> Sharing releases the
              photo under CC BY-SA 4.0. This is not a setting you can change later —
              anyone who already copied it under that licence keeps it, and a takedown
              here never reaches them.
            </p>
          </div>

          <div className="share-sheet__actions">
            <button
              type="button"
              className="share-sheet__share"
              data-testid="share-sheet-share"
              onClick={onShare}
            >
              Share with every hiker
            </button>
            <button
              type="button"
              className="share-sheet__cancel"
              data-testid="share-sheet-cancel"
              onClick={onClose}
            >
              Keep it private
            </button>
          </div>

          <p className="share-sheet__footnote">
            No signal is fine. This waits in your outbox and leaves when you have some —
            and it goes live about {COOLING_OFF_HOURS} hours after it sends. Until then,
            taking it back is a complete undo: nobody ever had it.
          </p>
        </>
      )}
    </div>
  )

  return createPortal(sheet, document.body)
}
