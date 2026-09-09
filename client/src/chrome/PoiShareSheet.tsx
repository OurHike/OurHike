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
// The exit stops at the map screen's root, not document.body (#1081). The
// card's transform is the box being escaped, and the screen root escapes it
// just as well - untransformed, so position:fixed still resolves against
// the viewport - while staying inside the subtree App.tsx hides and inerts
// when another screen covers the held map. A body portal floated this
// sheet, primary action and all, fully interactive over Settings the
// moment a tab switch hid the map underneath it. `document.body` remains
// the fallback for a caller that passes no container, which keeps the
// sheet's own tests rendering it bare.
//
// What this sheet never becomes (#577): no "share all", no default-on
// toggle, no count of anything. It appears when the hiker taps Share on
// their own photo, and declining is one tap that is never mentioned again.
//
// Since #837 the sheet also runs the on-device screen (lib/photoScreen.ts)
// while the hiker reads the terms, and a finding adds one step between
// "Share with every hiker" and the queue - the maintainer-adopted
// screening mockups ("Sharing a Photo" canvas, 2026-08-19), sentence for
// sentence. The step never refuses: faces get the fact and the same two
// buttons; nudity gets told a moderator looks first, and its primary
// button says what it now does ("Send it for review"). A screen that
// found nothing, or could not run at all, adds nothing - by contract the
// two are indistinguishable here (#570, flag never block).

import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { loadPreferences } from '../lib/preferences'
import { COOLING_OFF_HOURS } from '../lib/photoShare'
import { screenPhoto, type ScreenFinding } from '../lib/photoScreen'

export interface PoiShareSheetProps {
  /** Object URL of the stored 640px rendering - the exact bytes a share
   *  sends, previewed so "what they get" is the thing on screen. */
  photoUrl: string
  /** The stored bytes themselves, for the on-device screen (#837). */
  photoBlob: Blob
  /** Measured size of those bytes. */
  photoBytes: number
  /** The month the card prints for this photo, e.g. "Jun 2026". */
  photoMonth: string
  poiName: string
  /** Called with what the screen found, which rides the queued share as its
   *  `flagged` value - null both when nothing was found and when the check
   *  could not run, indistinguishably (see lib/photoScreen.ts). */
  onShare: (flagged: 'nudity' | 'faces' | null) => void
  onClose: () => void
  /** Where the portal lands - the map screen's root in the app, so the
   *  sheet hides and inerts with the held map (see the header). Null while
   *  that ref has not attached, and absent in bare test renders; both fall
   *  back to document.body. */
  container?: HTMLElement | null
}

/** "One face" / "Two faces" / "11 faces" - the mockup's headline counts in
 *  words, and past what a photo plausibly holds the digits are honest. */
function faceCount(faces: number): string {
  const words = [
    'No',
    'One',
    'Two',
    'Three',
    'Four',
    'Five',
    'Six',
    'Seven',
    'Eight',
    'Nine',
  ]
  const count = words[faces] ?? String(faces)
  return `${count} ${faces === 1 ? 'face' : 'faces'}`
}

interface SheetIdentity {
  trailName: string | null
  anonymityDays: number
}

export function PoiShareSheet({
  photoUrl,
  photoBlob,
  photoBytes,
  photoMonth,
  poiName,
  onShare,
  onClose,
  container,
}: PoiShareSheetProps) {
  // The two identity facts the sheet's sentences turn on, read from the
  // device's own preferences: who the credit names, and whether the
  // anonymity window will withhold it for a while. Null until loaded -
  // the sheet renders its facts only once it can state them truthfully.
  const [identity, setIdentity] = useState<SheetIdentity | null>(null)

  // The on-device screen (#837), started the moment the sheet opens so it
  // runs while the hiker reads. A ref rather than state because nothing
  // renders from it until Share is tapped - the tap awaits this promise,
  // which by then has usually settled.
  const screening = useRef<Promise<ScreenFinding> | null>(null)
  useEffect(() => {
    screening.current ??= screenPhoto(photoBlob)
  }, [photoBlob])

  // Which face of the sheet is up: the terms, or the screening step a
  // finding earns. `checking` covers the gap between tapping Share and the
  // screen settling - normally imperceptible, real on a first-ever share
  // where the models are still arriving.
  const [found, setFound] = useState<ScreenFinding>(null)
  const [step, setStep] = useState<'terms' | 'screen'>('terms')
  const [checking, setChecking] = useState(false)
  // The nudity step hides the preview until tapped - the mockup's own
  // treatment: the sheet must not display to a shoulder-surfer what it is
  // telling the hiker a moderator has to look at first.
  const [revealed, setRevealed] = useState(false)

  const proceed = async () => {
    setChecking(true)
    // The seam promises never to reject; the catch is for the day that
    // promise breaks, because the price here would be a Share button that
    // silently does nothing.
    const finding = await (screening.current ?? Promise.resolve(null)).catch(() => null)
    setChecking(false)
    if (finding === null) {
      onShare(null)
      return
    }
    setFound(finding)
    setStep('screen')
  }

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
        {step === 'screen' && found?.flag === 'nudity' && !revealed ? (
          // The mockup's own treatment: the sheet must not show a
          // shoulder-surfer what it is saying a moderator looks at first.
          <button
            type="button"
            className="share-sheet__hidden-preview"
            data-testid="share-sheet-reveal"
            onClick={() => setRevealed(true)}
          >
            Hidden until you tap
          </button>
        ) : (
          <img className="share-sheet__preview" src={photoUrl} alt="" />
        )}
        <div className="share-sheet__facts">
          <p className="share-sheet__poi">{poiName}</p>
          <p className="share-sheet__meta">
            {photoMonth} · 640 px · {Math.max(1, Math.round(photoBytes / 1024))} KB
          </p>
        </div>
      </div>

      {step === 'screen' && found !== null ? (
        found.flag === 'faces' ? (
          <div className="share-sheet__screen" data-testid="share-sheet-screen-faces">
            <h3>{faceCount(found.faces)} found on this phone</h3>
            <p>There are faces in this photo, and a public share puts them on a map.</p>
            <p>
              That is often the whole point — a photo of the shelter where you met your
              tramily is exactly what this is for. But the people in it are not here to be
              asked, and the licence you are about to attach cannot be taken back on their
              behalf either.
            </p>
            <p>
              <strong>This is not a refusal.</strong> Nothing is being blocked, and
              nothing left your phone to work it out. The check ran here and it only
              answers <em>is there a face</em>. It doesn’t know whether anyone is
              recognisable, and it didn’t ask them. It will also miss some.
            </p>
            <div className="share-sheet__actions">
              <button
                type="button"
                className="share-sheet__share"
                data-testid="share-sheet-share-faces"
                onClick={() => onShare('faces')}
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
          </div>
        ) : (
          <div className="share-sheet__screen" data-testid="share-sheet-screen-nudity">
            <h3>This one goes to a person before it goes public.</h3>
            <p>
              The check on your phone thinks there is nudity here. It is often wrong about
              that — a swimming hole in July looks the same to it — so it does not get to
              decide. A moderator at the maintaining club does.
            </p>
            <p>
              You can still send it. It just will not appear on the card until somebody
              has looked, and no licence attaches until it does.
            </p>
            <p>
              This is not a refusal and it is not a rejection — it is the only case where
              a stranger sees the photo before the trail does.
            </p>
            <div className="share-sheet__actions">
              <button
                type="button"
                className="share-sheet__share"
                data-testid="share-sheet-send-review"
                onClick={() => onShare('nudity')}
              >
                Send it for review
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
          </div>
        )
      ) : identity === null ? null : identity.trailName === null ? (
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
              disabled={checking}
              onClick={() => void proceed()}
            >
              {checking
                ? 'Looking at the photo on this phone…'
                : 'Share with every hiker'}
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

  return createPortal(sheet, container ?? document.body)
}
