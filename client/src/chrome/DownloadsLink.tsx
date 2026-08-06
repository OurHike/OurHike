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
}

export function DownloadsLink({ onOpen, hasDownload = false }: DownloadsLinkProps) {
  return (
    <button type="button" className="downloads-link" onClick={onOpen}>
      {hasDownload ? "Change what's downloaded" : 'Choose what to download'}
    </button>
  )
}
