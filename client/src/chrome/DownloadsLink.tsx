// The way to the download window, at the foot of whatever screen it is on.
//
// It is the only route there since the Downloads tab went (chrome/tabs.ts),
// which is a reason to keep it findable and not a reason to give it the space
// the eye lands on first. One whole-corridor package is downloaded once and
// deleted maybe never, so a hiker opens this a handful of times ever - against
// a legend they open all day. It goes last, under a rule, where a footer link
// goes: present, not competing.
//
// It began directly under the background picker, on the grounds that the
// picker is the only control in the app that mentions the downloaded map. The
// reasoning was right and the placement was not: the picker is the FIRST thing
// in the legend, so a link beneath it sat near the top of the panel - prime
// space for a rare errand. What that placement was buying is kept in words
// instead. The picker's own note already says a download is what makes
// "downloaded only" mean anything, and choosing that background with an empty
// phone opens the window on its own (App.tsx), so nobody has to find this link
// to get there.
//
// One component in two homes - the legend and Settings - rather than a copy in
// each, for the same reason BackgroundPicker is one component: two copies of a
// control drift, and then the app has two names for one thing.
//
// SINCE THE BAR, IT IS ALSO THE ONLY PLACE A DOWNLOAD IN PROGRESS IS VISIBLE
// FROM OUTSIDE ITS WINDOW. The transfer belongs to the shell, not to the
// window it was started from, so shutting that window left an app that looked
// idle while it spent someone's data - and the only way to check was to open
// the window again and hope. A rare errand does not earn a permanent readout;
// an errand that is HAPPENING RIGHT NOW does, for exactly as long as it is
// happening, and the link is already where somebody would go to look.

import { downloadPercent, type DownloadActivity } from '../lib/downloadActivity'

/** What the footer calls each wait. Two words at most, because this sits
 *  beside a label it must not outweigh - and the differences matter enough to
 *  say: one is spending signal, one is the phone reading its own disk (#197),
 *  and one is the trail data that has to arrive before either. The window is
 *  where each is explained in full. */
const ACTIVITY_WORD: Record<DownloadActivity['kind'], string> = {
  preparing: 'Getting trail data',
  downloading: 'Downloading',
  checking: 'Checking',
}

export interface DownloadsLinkProps {
  onOpen: () => void
  /**
   * Whether a finished corridor archive is on this phone, which is the whole
   * difference between choosing a download and changing one.
   *
   * Two labels rather than one because "choose what to download" is wrong for
   * someone who already has 314 MB of it, and "change your download" is a
   * claim about a phone that may have nothing on it at all.
   */
  hasDownload?: boolean
  /**
   * What is arriving right now, or null when nothing is
   * (lib/downloadActivity.ts).
   *
   * Absent by default, and absent is silence: a footer that reserved room for
   * a bar would spend that room on every screen for the sake of the few
   * minutes a year one is moving. It appears when there is something to say
   * and goes when there is not.
   */
  downloadActivity?: DownloadActivity | null
}

export function DownloadsLink({
  onOpen,
  hasDownload = false,
  downloadActivity = null,
}: DownloadsLinkProps) {
  // Null while the trail data is still coming, and that is the honest answer
  // rather than a placeholder 0%: those are four fetches of unannounced size,
  // so there is no figure to round. The word alone carries it, and the bar
  // arrives with the transfer it measures.
  const percent =
    downloadActivity === null || downloadActivity.kind === 'preparing'
      ? null
      : downloadPercent(downloadActivity.doneBytes, downloadActivity.totalBytes)

  return (
    // The bar lives INSIDE the button rather than beside it, and that is a
    // thumb decision before it is a markup one: the bar is what the eye lands
    // on, so it is what a hiker taps, and a bar that is not part of the
    // control is a tap that does nothing. It carries no role of its own for
    // the same reason it cannot - a button's descendants are presentational to
    // a screen reader, so a `role="progressbar"` in here would be silently
    // dropped. The figure is said in the button's own text instead, which is
    // what gets announced: "Choose what to download. Downloading 38%."
    <button type="button" className="downloads-link" onClick={onOpen}>
      <span className="downloads-link__line">
        <span>
          {hasDownload ? "Change what's downloaded" : 'Choose what to download'}
        </span>
        {downloadActivity !== null && (
          <span className="downloads-link__status">
            {ACTIVITY_WORD[downloadActivity.kind]}
            {percent !== null && ` ${percent}%`}
            {percent === null && '…'}
          </span>
        )}
      </span>
      {percent !== null && (
        <span className="downloads-link__bar" aria-hidden="true">
          <span className="downloads-link__bar-fill" style={{ width: `${percent}%` }} />
        </span>
      )}
    </button>
  )
}
