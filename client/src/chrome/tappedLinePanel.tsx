// The tapped-line feature, owned by one file instead of by App.tsx (#327).
//
// One tap on the trail asks one question, and which question depends on the
// zoom: above the seam it is "what is this line" (#134), below it "who
// maintains this stretch" (features/CORRIDOR_VIEW.md). A tap on a highlight
// mark (#858) beats both. The three sheets are mutually exclusive by
// construction here, which is the property that made them worth extracting
// together rather than one at a time.
//
// See chrome/atcNoticesPanel.tsx for why this shape - a hook returning a
// `Pick<MapScreenProps, …>` the shell spreads - is the fix rather than a move.
//
// Two inputs are shared with a feature that stayed behind and are therefore
// passed in rather than derived here: `belowSeam` and `clubRuns` are also what
// the legend's maintainer line reads. Deriving them twice would have been two
// answers to one question, which is the failure App.tsx's own comments keep
// naming ("two surfaces measuring the same distance two ways").

import { useCallback, useEffect, useMemo, useState } from 'react'
import type { MapScreenProps } from './MapScreen'
import { LineSheet } from './LineSheet'
import { trailIdForSource } from '../map/trailBadges'
import { ClubSheet } from './ClubSheet'
import { HighlightSheet } from './HighlightSheet'
import { buildLineDetail, type LineDetail } from '../lib/lineDetail'
import { lineClimb, type LineClimb } from '../lib/lineClimb'
import { fetchTrailGraphElevationCells, type MergedGraph } from '../lib/trailGraphData'
import { buildClubDetail, type ClubDetail } from '../lib/clubDetail'
import { buildHighlightDetail, type HighlightDetail } from '../lib/highlightDetail'
import type { ClubRun, ClubSections } from '../lib/clubSections'
import type { Highlight } from '../lib/highlights'
import type { TappedLine } from '../map/lineTaps'
import type { MapSheets } from '../lib/mapSheets'
import { paperMapsAt, type PaperMapMatch } from '../lib/paperMaps'
import type { Stewards } from '../lib/stewards'
import type { SpurRecord } from '../lib/spurDestination'
import type { StoredPoi } from '../lib/trailData'
import type { TrailIndex } from '../lib/trailPosition'
import { mileOnTrail } from '../lib/trailPosition'
import type { ElevationProfile } from '../lib/elevationProfile'
import type { PaceProfile } from '../lib/pace'
import type { MileRange } from '../lib/walkedMiles'
import type { UnitSystem } from '../lib/userPreferences'

/** The `MapScreenProps` fields this feature owns. See atcNoticesPanel.tsx. */
export type TappedLineMapProps = Pick<
  MapScreenProps,
  'onSelectLine' | 'onSelectHighlight' | 'lineSheet'
>

export interface TappedLinePanel {
  /** Spread into `<MapScreen>`. */
  mapScreen: TappedLineMapProps
}

export interface TappedLineInput {
  spurs: Record<string, SpurRecord>
  pois: readonly StoredPoi[]
  units: UnitSystem
  trailName: string
  pace: PaceProfile
  /** Per-source attribution from the published stewards artifact (§6,
   *  #1142), so a closure's sentence can name the org that closed it in
   *  their own words. Empty until stewards load, which reads exactly as the
   *  sheet always read: sentences without a by-clause, never a made-up one. */
  trailSources: Readonly<Record<string, { attribution: string | null }>>
  /** Who the map's data belongs to (lib/stewards.ts): the paper maps each
   *  organization sells and which sheets they hold (#1574). Empty until the
   *  stewards load, which reads as no paper map, exactly as before. */
  stewards: Stewards
  /** The sheet footprints from the bucket's archive (lib/mapSheets.ts), or
   *  null while none has arrived - which reads as no paper map. */
  mapSheets: MapSheets | null
  walked: readonly MileRange[]
  /** The centerline, or null before it has loaded. */
  trailIndex: TrailIndex | null
  /** Whether the camera is below the corridor seam - the club sheet's gate.
   *  Passed in because the legend's maintainer line reads the same answer. */
  belowSeam: boolean
  clubSections: ClubSections
  /**
   * The junction graph as merged from the cells this phone holds (#1476), or
   * null before any lands. What the climb figure is summed out of: an edge
   * carries its parent line's `trail_id`, so the tapped feature's id selects
   * its own edges and nothing else.
   */
  graphMerged: MergedGraph | null
  /** Whether the climb half may be fetched with signal. Passed rather than
   *  assumed, for lib/trailGraphData.ts's reason: offline the store read is
   *  what makes this work at a trailhead instead of only at the hostel. */
  online: boolean
  /** The corridor read end to end, in mile order. Passed in for the same
   *  reason `belowSeam` is. */
  clubRuns: readonly ClubRun[]
  highlights: readonly Highlight[]
  elevation: ElevationProfile | null
  /** Closes the legend, which any tap that opens a sheet does. */
  onCloseLegend: () => void
  /**
   * Start a day hike from a tapped point on a trail (#979), or undefined when
   * this phone cannot - no junction graph, or no trail lines yet.
   *
   * Undefined rather than a no-op, so the sheet renders no control at all:
   * chrome/LineSheet.tsx's rule is a sentence, never a dead button, and this
   * hook is the layer that knows whether the router could use the tap.
   */
  onStartDayHikeAt?: (at: { lon: number; lat: number }) => void
  /**
   * The trail taken today (App.tsx's `chosenTrailId`) and whether a long
   * hike is what took it, for the sheet's take / let-go (the review of
   * #1374). Omitted, the sheet offers neither - every existing caller and
   * test is unaffected.
   */
  takenTrailId?: string | null
  takenByHike?: boolean
  /** Take a registry trail from the map, or null to let the tapped one go. */
  onTakeTrail?: (trailId: string | null) => void
}

/**
 * The sheet's take / let-go props for one tapped line, or nothing (the
 * review of #1374). Nothing where the line is not a registry trail or the
 * shell passed no handler: the sheet then draws neither, on its own rule.
 */
function takeProps(
  trailId: string | null,
  takenTrailId: string | null,
  takenByHike: boolean,
  onTakeTrail: ((trailId: string | null) => void) | undefined,
  close: () => void,
): Pick<React.ComponentProps<typeof LineSheet>, 'taken' | 'onTakeTrail' | 'onLetGo'> {
  if (trailId === null || onTakeTrail === undefined) return {}
  if (takenTrailId !== trailId) {
    return {
      taken: null,
      onTakeTrail: () => {
        onTakeTrail(trailId)
        close()
      },
    }
  }
  if (takenByHike) return { taken: 'hike' }
  return {
    taken: 'tap',
    onLetGo: () => {
      onTakeTrail(null)
      close()
    },
  }
}

export function useTappedLinePanel({
  spurs,
  pois,
  units,
  trailName,
  pace,
  trailSources,
  stewards,
  mapSheets,
  walked,
  trailIndex,
  belowSeam,
  clubSections,
  clubRuns,
  graphMerged,
  online,
  highlights,
  elevation,
  onCloseLegend,
  onStartDayHikeAt,
  takenTrailId = null,
  takenByHike = false,
  onTakeTrail,
}: TappedLineInput): TappedLinePanel {
  /** The tapped trail line's published facts, or null (#134). The map
   *  reports them (map/lineTaps.ts); what they mean - the spur record, the
   *  destination's name - is resolved here, where the data is. */
  const [selectedLine, setSelectedLine] = useState<TappedLine | null>(null)
  const [selectedHighlightId, setSelectedHighlightId] = useState<string | null>(null)

  /**
   * The climb half of the graph cells this phone holds, and the graph it was
   * fetched for (#1476).
   *
   * PAIRED WITH ITS GRAPH RATHER THAN KEPT ALONE, because the merge is
   * append-only: a cell landing after this was fetched leaves the array
   * shorter than the edges it would be read against, and an array priced
   * against the wrong edges is a plausible figure on the wrong trail. Holding
   * the graph beside it makes the staleness checkable in one `===` instead of
   * inferred from a length.
   *
   * `data: null` is a DECIDED absence - published without the climb half, or
   * a 404 - and is recorded so it is not re-asked on every tap. An undecided
   * answer (the network refused) is deliberately NOT recorded: nothing was
   * learned, so the next tap may ask again. That is lib/trailGraphData.ts's
   * own three-way distinction, kept rather than flattened here.
   */
  const [heldClimb, setHeldClimb] = useState<{
    graph: MergedGraph
    data: Array<[number, number] | null> | null
  } | null>(null)

  // FETCHED ON THE TAP, not at launch. The climb half is small beside the
  // shard it aligns with, but it is not free, and a hiker who never taps a
  // line never needs it - the same lazily-when-a-door-opens shape the builder
  // uses for the geometry half.
  const wantsClimb = selectedLine !== null
  useEffect(() => {
    if (!wantsClimb || graphMerged === null) return
    if (heldClimb?.graph === graphMerged) return

    const controller = new AbortController()
    let wanted = true
    void fetchTrailGraphElevationCells(graphMerged, controller.signal, online).then(
      (outcome) => {
        if (!wanted || outcome.kind === 'undecided') return
        setHeldClimb({
          graph: graphMerged,
          data: outcome.kind === 'loaded' ? outcome.data : null,
        })
      },
    )

    return () => {
      wanted = false
      controller.abort()
    }
  }, [wantsClimb, graphMerged, heldClimb, online])

  /**
   * What this phone can honestly say about the tapped line's climb.
   *
   * The array is used only while it still belongs to the graph in hand;
   * otherwise nothing is passed and `lineClimb` reads whatever the edges
   * themselves carry, which for a plain merged shard is nothing at all - the
   * honest "no figures" rather than a figure summed against stale alignment.
   */
  const climb: LineClimb = useMemo(() => {
    if (selectedLine === null || graphMerged === null) return { kind: 'none' }
    return lineClimb(
      graphMerged.graph,
      selectedLine,
      heldClimb?.graph === graphMerged ? heldClimb.data : null,
    )
  }, [selectedLine, graphMerged, heldClimb])

  /**
   * The tapped line's sheet content (#134), resolved here for the reason
   * `selectedPoi` is: the map reports what was drawn, and the shell is what
   * holds the spur records, the POI a spur leads to, and the hiker's units.
   */
  /**
   * Which paper maps hold the tapped point (#1574), resolved here for the
   * reason the club sheet's mile is: the map reports where the tap landed,
   * snapped to the line (map/lineTaps.ts), and the shell holds the stewards
   * and the footprints. Every match rather than the first: two sets'
   * footprints can overlap at a margin (Sterling Forest's box and Harriman's
   * do, around Tuxedo), and a spot on both is on both.
   */
  const paperMaps: readonly PaperMapMatch[] = useMemo(() => {
    if (selectedLine === null) return []
    return paperMapsAt(
      stewards,
      mapSheets,
      'trail_sheet',
      selectedLine.at[0],
      selectedLine.at[1],
    )
  }, [selectedLine, stewards, mapSheets])

  const lineDetail: LineDetail | null = useMemo(() => {
    if (selectedLine === null) return null
    return buildLineDetail(
      selectedLine,
      spurs,
      pois,
      units,
      trailName,
      pace,
      trailSources,
      climb,
      paperMaps,
    )
  }, [selectedLine, spurs, pois, units, trailName, pace, trailSources, climb, paperMaps])

  const clubDetail: ClubDetail | null = useMemo(() => {
    if (!belowSeam || selectedLine === null || trailIndex === null) return null
    // The tapped point is already snapped to the line (map/lineTaps.ts), so
    // this is asking "which mile is that vertex" rather than "is the thumb
    // near the trail" - which at this zoom it need not be.
    const mile = mileOnTrail(trailIndex, {
      lon: selectedLine.at[0],
      lat: selectedLine.at[1],
    })
    if (mile === null) return null
    return buildClubDetail(clubSections, clubRuns, mile, units, walked)
  }, [belowSeam, selectedLine, trailIndex, clubSections, clubRuns, units, walked])

  /**
   * The tapped highlight's sheet content (#858).
   *
   * Resolved here for the reason the club sheet is: the map reports which
   * mark was touched, and the shell is what holds the records, the elevation
   * profile the numbers are derived from, the hiker's units and what they
   * have walked.
   */
  const highlightDetail: HighlightDetail | null = useMemo(() => {
    if (selectedHighlightId === null) return null
    const highlight = highlights.find((entry) => entry.id === selectedHighlightId)
    if (highlight === undefined) return null
    return buildHighlightDetail(highlight, elevation, units, walked, pace)
  }, [selectedHighlightId, highlights, elevation, units, walked, pace])

  // The line taps report on every click, nulls included, exactly as the POI
  // taps do - the null is the tap-elsewhere dismissal, and it also fires
  // when a tap lands on a pin or an ATC notice (map/lineTaps.ts yields to
  // both), which is what keeps this sheet from stacking under theirs.
  // A tapped mark closes the legend the way a tapped line does, and clears
  // the line selection so the two sheets can never both be open.
  const handleSelectHighlight = useCallback(
    (id: string | null) => {
      setSelectedHighlightId(id)
      if (id !== null) {
        onCloseLegend()
        setSelectedLine(null)
      }
    },
    [onCloseLegend],
  )

  const handleSelectLine = useCallback(
    (line: TappedLine | null) => {
      setSelectedLine(line)
      if (line !== null) onCloseLegend()
    },
    [onCloseLegend],
  )

  const mapScreen = useMemo<TappedLineMapProps>(
    () => ({
      onSelectLine: handleSelectLine,
      onSelectHighlight: handleSelectHighlight,
      lineSheet:
        // A tapped highlight wins over both: it is a small, aimed-at mark
        // sitting ON the corridor, the same rule map/lineTaps.ts applies
        // when a pin beats the line under it.
        highlightDetail !== null ? (
          <HighlightSheet
            detail={highlightDetail}
            onClose={() => setSelectedHighlightId(null)}
          />
        ) : // The club sheet wins below the seam, and the two never stack:
        // one tap asks one question, and which question it is depends on
        // what the map is showing.
        clubDetail !== null ? (
          <ClubSheet detail={clubDetail} onClose={() => setSelectedLine(null)} />
        ) : lineDetail === null ? null : (
          <LineSheet
            detail={lineDetail}
            onClose={() => setSelectedLine(null)}
            {...takeProps(
              selectedLine === null ? null : trailIdForSource(selectedLine.source),
              takenTrailId,
              takenByHike,
              onTakeTrail,
              () => setSelectedLine(null),
            )}
            // The tapped point is already snapped to the line by
            // map/lineTaps.ts, so what goes to the builder is a place on a
            // trail rather than wherever the thumb landed.
            onAddToDayHike={
              onStartDayHikeAt !== undefined && selectedLine !== null
                ? () => {
                    onStartDayHikeAt({
                      lon: selectedLine.at[0],
                      lat: selectedLine.at[1],
                    })
                    setSelectedLine(null)
                  }
                : undefined
            }
          />
        ),
    }),
    [
      handleSelectLine,
      handleSelectHighlight,
      highlightDetail,
      clubDetail,
      lineDetail,
      selectedLine,
      onStartDayHikeAt,
      takenTrailId,
      takenByHike,
      onTakeTrail,
    ],
  )

  return { mapScreen }
}
