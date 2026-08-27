// The ATC-notices feature, owned by one file instead of by App.tsx (#327).
//
// Everything the map screen needs in order to draw the ATC's notices, let a
// hiker tap one, and tell them when new ones have been posted: the two map
// collections, the tap handler, the sheet over the tapped one, the full list,
// and the "new alerts" banner's count and its dismissal.
//
// All of it used to live in App.tsx as three `useState`s, five `useMemo`s, one
// `useCallback` and about forty lines of JSX inside the `<MapScreen>` call -
// at roughly lines 640, 1,490 and 4,440 of a 4,706-line file, each block
// interleaved with every other feature's share of the same four things. That
// interleaving is the mechanism #327 measured: a change to ATC notices and a
// change to, say, the route builder both edit App.tsx, so the two branches
// conflict even though the features have nothing to do with each other.
//
// What makes this more than a move is the return type. The hook hands back
// exactly the `MapScreenProps` fields this feature owns, as a `Pick<>`, so
// App.tsx spreads one value and the bundle cannot drift from the screen's own
// declarations. Ownership itself is a convention rather than something the
// compiler enforces - nothing stops a second file `Pick`ing the same field -
// but it is a convention with one obvious place to check, which is more than
// a flat prop list offers.
//
// MapScreen itself is untouched: its prop list is still flat, and that is
// deliberate. Regrouping its 104 props into bundles would have rewritten
// every fixture in MapScreen.test.tsx, which is churn that hides behaviour
// rather than protecting it.

import { useCallback, useMemo, useState } from 'react'
import {
  atcBandCandidates,
  atcPointNotices,
  atcUpdateForBandId,
  type AtcUpdate,
} from '../lib/atcUpdates'
import { atcUpdatePoints } from '../map/atcUpdateLayers'
import {
  atcAlertsSince,
  readAtcAlertSilence,
  writeAtcAlertSilence,
} from '../lib/atcAlertsBanner'
import { closureBands } from '../map/closureLayers'
import type { TrailIndex } from '../lib/trailPosition'
import type { MapScreenProps } from './MapScreen'
import { AtcUpdateSheet } from './AtcUpdateSheet'
import { AtcNoticeList } from './AtcNoticeList'

/**
 * The `MapScreenProps` fields this feature owns.
 *
 * A `Pick<>` rather than a hand-written interface so it cannot drift from the
 * screen's own declarations - the prose explaining each of these lives on
 * `MapScreenProps`, where the component that renders them can be read beside
 * it, and is deliberately not copied here.
 */
export type AtcNoticesMapProps = Pick<
  MapScreenProps,
  | 'atcUpdates'
  | 'atcUpdatePoints'
  | 'onSelectAtcUpdate'
  | 'atcUpdateSheet'
  | 'atcNoticeCount'
  | 'onOpenAtcNotices'
  | 'atcNoticeList'
  | 'newAtcAlertCount'
  | 'onSilenceNewAtcAlerts'
>

export interface AtcNoticesPanel {
  /** Spread into `<MapScreen>`. */
  mapScreen: AtcNoticesMapProps
  /**
   * Whether a hiker has one of this feature's sheets open.
   *
   * Returned separately rather than folded into `mapScreen` because it is not
   * a prop: the shell reads it to decide whether a service-worker update may
   * restart the page under somebody (lib/useAppUpdate.ts). Only the tapped
   * sheet counts, exactly as it did in App.tsx - the notice list is a list a
   * hiker can reopen, and the banner is not a screen at all.
   */
  sheetOpen: boolean
}

export interface AtcNoticesInput {
  /** Every notice the app holds (lib/useConditions.ts). */
  updates: readonly AtcUpdate[]
  /** When a person last checked the reviewed file against ATC's page. */
  reviewedAt: Date | null
  /** The centerline, or null before it has loaded - nothing is placed without it. */
  trailIndex: TrailIndex | null
  /** The shell's clock, so the "new alerts" window moves with it. */
  now: Date
}

export function useAtcNoticesPanel({
  updates,
  reviewedAt,
  trailIndex,
  now,
}: AtcNoticesInput): AtcNoticesPanel {
  const [selectedBandId, setSelectedBandId] = useState<string | null>(null)
  /**
   * Whether the full list of ATC notices is open.
   *
   * Separate from `selectedBandId` rather than a third state of it. The two
   * answer different questions - "which one did they tap" and "did they ask to
   * read all of them" - and a hiker who opens the list, taps a band behind it
   * and closes that sheet should find the list still where they left it.
   */
  const [noticesOpen, setNoticesOpen] = useState(false)
  /** The newest ATC edit the hiker has already silenced on this phone, or
   *  null - lib/atcAlertsBanner.ts's watermark, read once at mount and
   *  written back every time silencing happens. */
  const [alertSilence, setAlertSilence] = useState<Date | null>(() =>
    readAtcAlertSilence(),
  )

  /**
   * The ATC's notices as bands, through exactly the same geometry.
   *
   * `atcBandCandidates` adapts each update into the shared `Closure` shape and
   * `closureBands` does the rest, so an ATC update inherits `trailSlice`'s
   * centerline placement and `isBroadAdvisory`'s length ceiling without either
   * being reimplemented - which is what #461 means by the geometry path
   * needing no new code, and what keeps ATC's 398-mile Helene advisory from
   * painting a fifth of the trail (#462).
   *
   * The candidate filter is where the two differ: only ATC categories that
   * mean the trail itself is obstructed become a band, because barrier tape
   * says "go around" and a notice about a closed car park does not. The rest
   * keep the banner, exactly as an over-long advisory does.
   */
  const bandsOnMap = useMemo(() => {
    if (trailIndex === null) return []
    return closureBands(atcBandCandidates(updates), trailIndex)
  }, [updates, trailIndex])

  /**
   * The same notices that name one mile rather than a stretch, as dots.
   *
   * Not filtered by `obstructsTheTrail`, unlike the bands. A dot makes no
   * claim about passability - it says the ATC has posted something here - so a
   * bear warning and a closed shelter both belong on the map, and neither is
   * the barrier a band would have made them.
   */
  const pointsOnMap = useMemo(() => {
    if (trailIndex === null) return []
    return atcUpdatePoints(atcPointNotices(updates), trailIndex)
  }, [updates, trailIndex])

  /** The tapped update, resolved from the band id the map reported. */
  const selectedUpdate = useMemo(() => {
    if (selectedBandId === null) return null
    return atcUpdateForBandId(updates, selectedBandId)
  }, [updates, selectedBandId])

  /**
   * Which notices the canvas is ACTUALLY drawing, by band id.
   *
   * Read off the two collections above rather than re-derived from the
   * updates, and that is the whole point of computing it here. The filters
   * (`atcBandCandidates`, `atcPointNotices`) say what this build INTENDS to
   * draw; `closureBands` and `atcUpdatePoints` then drop anything whose mile
   * falls outside this build's centerline, which no predicate over an
   * `AtcUpdate` can know. AtcNoticeList tells a hiker which notices have no
   * mark to look for, and it can only be honest about that from the truth.
   */
  const drawnIds = useMemo(
    () =>
      new Set<string>([
        ...bandsOnMap.map((band) => band.id),
        ...pointsOnMap.map((point) => point.id),
      ]),
    [bandsOnMap, pointsOnMap],
  )

  /**
   * What the bottom "new alerts" banner has to say, or null (#687).
   *
   * Independent of every filter above - `atcBandCandidates`, `atcPointNotices`
   * and the lane functions all decide what belongs on the MAP or in the
   * header's one line, and none of that is "has ATC posted something
   * recently". An update the map cannot place and the header will never
   * mention (behind the hiker, over the band ceiling) is still new, and
   * still worth this banner - `chrome/AtcNoticeList.tsx` is the same
   * argument for the full list.
   */
  const newAlerts = useMemo(
    () => atcAlertsSince(updates, now, alertSilence),
    [updates, now, alertSilence],
  )

  const silenceAlerts = useCallback(() => {
    if (newAlerts === null) return
    writeAtcAlertSilence(newAlerts.newestAt)
    setAlertSilence(newAlerts.newestAt)
  }, [newAlerts])

  const openNotices = useCallback(() => {
    setNoticesOpen(true)
    // Opening the full list is a hiker having looked, exactly as much as
    // tapping the bottom banner's own dismiss is - see silenceAlerts above.
    silenceAlerts()
  }, [silenceAlerts])

  const mapScreen = useMemo<AtcNoticesMapProps>(
    () => ({
      atcUpdates: bandsOnMap,
      atcUpdatePoints: pointsOnMap,
      onSelectAtcUpdate: setSelectedBandId,
      atcUpdateSheet:
        selectedUpdate === null ? null : (
          <AtcUpdateSheet
            update={selectedUpdate}
            reviewedAt={reviewedAt}
            onClose={() => setSelectedBandId(null)}
          />
        ),
      atcNoticeCount: updates.length,
      onOpenAtcNotices: openNotices,
      newAtcAlertCount: newAlerts?.count ?? 0,
      onSilenceNewAtcAlerts: silenceAlerts,
      atcNoticeList: noticesOpen ? (
        <AtcNoticeList
          updates={updates}
          drawnIds={drawnIds}
          reviewedAt={reviewedAt}
          onClose={() => setNoticesOpen(false)}
        />
      ) : null,
    }),
    [
      bandsOnMap,
      pointsOnMap,
      selectedUpdate,
      reviewedAt,
      updates,
      openNotices,
      newAlerts,
      silenceAlerts,
      noticesOpen,
      drawnIds,
    ],
  )

  return { mapScreen, sheetOpen: selectedBandId !== null }
}
