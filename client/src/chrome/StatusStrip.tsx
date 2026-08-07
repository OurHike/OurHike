// The strip where the map admits what it doesn't know (WIREFRAMES.md §1).
//
// Time, connectivity, GPS fix, and how old the data is. Being offline or
// losing the fix is a normal condition on trail, not an error - but it has to
// be SAID, because the failure mode this strip exists to prevent is a stale
// position rendered exactly like a live one. Silence would read as "this is
// where you are" when the honest answer is "this is where you last were."

import { syncAgeLabel } from '../lib/syncAge'
import type { BackgroundOverride } from '../lib/dataSaver'
import type { BackgroundProblem } from '../lib/backgroundHealth'

/**
 * What each problem is called on a strip this narrow (lib/backgroundHealth.ts
 * decides which one applies).
 *
 * Three or four words each, and each one names the half a hiker can act on:
 * a download that is not drawing sends them to the Downloads screen, and a
 * download they do not have sends them to town first. "No live map" is
 * carried over verbatim from the flag this replaced, because its case and its
 * meaning are unchanged.
 */
const BACKGROUND_PROBLEM_LABEL: Record<BackgroundProblem, string> = {
  'download-not-drawing': 'Downloaded map not drawing',
  'live-unreachable': 'No live map',
  'nothing-to-draw': 'No downloaded map',
}

export interface StatusStripProps {
  time: Date
  online: boolean
  hasGpsFix: boolean
  /** When the on-device data last synced; null if it never has. */
  lastSyncedAt: Date | null
  /**
   * Why the background is not on screen, or null when it is - decided by
   * lib/backgroundHealth.ts from what the map's sources reported and what is
   * actually downloaded.
   *
   * This used to be `liveBackgroundUnavailable`, a boolean about the live
   * sheet alone, and it was rendered only while `online` on the reasoning that
   * "Offline already accounts for the paper". That reasoning holds for a phone
   * with nothing downloaded and fails for every other phone: it is what kept
   * the strip silent about a damaged archive and about a hiking sheet deleted
   * an hour ago, which is to say silent in exactly the two cases where the
   * hiker cannot work out what happened (#314). The connectivity question is
   * now one input to the decision rather than a gate on whether it is allowed
   * to be reported.
   */
  backgroundProblem?: BackgroundProblem | null
  /**
   * Why the background on screen is not the one in settings, if it isn't -
   * see lib/dataSaver.ts.
   *
   * That module's rule is that the app "is allowed to override a preference,
   * and is not allowed to do it silently," and until now the only screen that
   * said so was Settings. The map screen is where an overridden background is
   * actually visible, so it is where the reason belongs too.
   */
  backgroundOverride?: BackgroundOverride | null
  /**
   * Whether the view is zoomed out past what the download covers (#216).
   *
   * A sibling of `backgroundOverride` rather than one of its reasons, because
   * it is a different claim: nothing has been overridden, the chosen
   * background is exactly what is drawn, and it simply has no tiles at this
   * scale. Saying "your background was overridden" here would be false, and
   * saying nothing was what let a complete 314 MB download look like a broken
   * app for two zoom levels.
   */
  belowArchiveZoom?: boolean
}

export function StatusStrip({
  time,
  online,
  hasGpsFix,
  lastSyncedAt,
  backgroundProblem = null,
  backgroundOverride = null,
  belowArchiveZoom = false,
}: StatusStripProps) {
  return (
    <div className="status-strip">
      <span className="status-strip__time">
        {time.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
      </span>

      {/* Polite, not assertive: losing signal mid-walk is expected, and should
          never interrupt whatever the hiker is already reading. */}
      <span className="status-strip__conditions" role="status">
        {!online && <span className="status-strip__flag">Offline</span>}
        {!hasGpsFix && <span className="status-strip__flag">No GPS fix</span>}
        {backgroundProblem !== null && (
          <span className="status-strip__flag">
            {BACKGROUND_PROBLEM_LABEL[backgroundProblem]}
          </span>
        )}
        {/* Two reasons, opposite in kind: one says the app is withholding the
            live sheet, the other that it is supplying it against a preference
            that has no download to honour yet. One word of the wrong one is a
            map that lies about what it is doing with someone's data. */}
        {backgroundOverride === 'data-saver' && (
          <span className="status-strip__flag">Data Saver: downloaded map only</span>
        )}
        {/* Dropped when the background has a problem of its own, which is the
            one place these two can both fire and only one can be useful.
            "Live map — nothing downloaded yet" describes what the app is
            TRYING to draw; a problem above says what is actually arriving,
            which is nothing. Both at once is two flags for one blank screen,
            and the reassuring one reads first. */}
        {backgroundOverride === 'nothing-downloaded' && backgroundProblem === null && (
          <span className="status-strip__flag">Live map — nothing downloaded yet</span>
        )}
        {/* Not a background override, and kept out of that type on purpose.
            The two above say the app is DRAWING something other than what was
            chosen. This one says the choice is being honoured exactly and has
            nothing to draw at this scale, because the download starts closer
            in (#216). Folding it into BackgroundOverride would mean
            effectiveBackground changing as the hiker zooms - and MapView
            rebuilds the whole WebGL map when the background changes, so
            crossing that zoom would tear the map down and build it again,
            repeatedly, while someone pinched. */}
        {belowArchiveZoom && (
          <span className="status-strip__flag">Zoomed out past your download</span>
        )}
      </span>

      <span className="status-strip__sync">{syncAgeLabel(lastSyncedAt, time)}</span>
    </div>
  )
}
