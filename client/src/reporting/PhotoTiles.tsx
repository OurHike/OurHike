// A report's photos as a row of tiles (#1439, frame 9f; #1563), rendered by
// the long form and by the report window's receipt over one state machine
// (reporting/useReportPhotos.ts).
//
// SEVERAL PHOTOS, EACH SHRUNK ON PICK, EACH ITS OWN TILE. A blowdown is three
// trunks and one photo rarely shows it. The shrink stays on pick, per #234's
// reasoning and once per tile: the only failure a hiker can do anything
// about is "take another one", and they can only do that while still
// standing in front of the thing they photographed. Independently, so one
// that will not go says so under its own tile and the rest stay attached -
// which is the difference between losing a photo and losing them all.

import { MAX_REPORT_PHOTOS } from '../lib/reportPhoto'
import { photoSummary, type ReportPhotos } from './useReportPhotos'
import './photoTiles.css'

export type PhotoTilesProps = Pick<
  ReportPhotos,
  'picks' | 'ready' | 'full' | 'choosePhoto' | 'removePick'
>

export function PhotoTiles({
  picks,
  ready,
  full,
  choosePhoto,
  removePick,
}: PhotoTilesProps) {
  return (
    <>
      <ul className="reporting__photos">
        {picks.map((pick) => (
          <li
            key={pick.id}
            className={
              pick.state === 'failed'
                ? 'reporting__tile reporting__tile--failed'
                : 'reporting__tile'
            }
          >
            {pick.state === 'ready' && (
              <img className="reporting__thumb" src={pick.url} alt="" />
            )}
            {pick.state === 'preparing' && (
              <span className="reporting__tile-state" role="status">
                shrinking…
              </span>
            )}
            {pick.state === 'failed' && (
              <span className="reporting__tile-state" role="alert">
                {pick.message}
              </span>
            )}
            {/* One remove per tile, and it works in every state: a hiker who
                picked the wrong photo must not have to wait for the wrong
                photo to finish shrinking before they can take it back. */}
            <button
              type="button"
              className="reporting__tile-remove"
              aria-label={`Remove photo ${picks.indexOf(pick) + 1}`}
              onClick={() => removePick(pick.id)}
            >
              ×
            </button>
          </li>
        ))}
        {!full && (
          <li className="reporting__tile reporting__tile--add">
            <label className="reporting__add">
              <span aria-hidden="true">+</span>
              <span className="reporting__add-label">Add a photo</span>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp,image/heic"
                className="reporting__photo"
                onChange={(event) => {
                  void choosePhoto(event.target.files?.[0] ?? null)
                  // Cleared so picking the SAME file twice still fires a
                  // change - a hiker retaking a photo that failed is the
                  // commonest second pick there is.
                  event.target.value = ''
                }}
              />
            </label>
          </li>
        )}
      </ul>
      {/* THE CEILING IS A SENTENCE, NOT A GREYED TILE (D10): a control that
          looks pressable and is not teaches a hiker at a junction that the
          app is broken. Past the cap the `+` is gone and this says why. */}
      {full && (
        <span className="reporting__meta">
          {`That is ${MAX_REPORT_PHOTOS} photos, which is as many as one report carries. Remove one to add another.`}
        </span>
      )}
      {ready.length > 0 && (
        <span className="reporting__meta">
          {`${photoSummary(ready)}. Location and camera details are not included.`}
        </span>
      )}
    </>
  )
}
