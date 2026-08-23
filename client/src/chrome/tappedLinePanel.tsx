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

import { useCallback, useMemo, useState } from 'react'
import type { MapScreenProps } from './MapScreen'
import { LineSheet } from './LineSheet'
import { ClubSheet } from './ClubSheet'
import { HighlightSheet } from './HighlightSheet'
import { buildLineDetail, type LineDetail } from '../lib/lineDetail'
import { buildClubDetail, type ClubDetail } from '../lib/clubDetail'
import { buildHighlightDetail, type HighlightDetail } from '../lib/highlightDetail'
import type { ClubRun, ClubSections } from '../lib/clubSections'
import type { Highlight } from '../lib/highlights'
import type { TappedLine } from '../map/lineTaps'
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
  walked: readonly MileRange[]
  /** The centerline, or null before it has loaded. */
  trailIndex: TrailIndex | null
  /** Whether the camera is below the corridor seam - the club sheet's gate.
   *  Passed in because the legend's maintainer line reads the same answer. */
  belowSeam: boolean
  clubSections: ClubSections
  /** The corridor read end to end, in mile order. Passed in for the same
   *  reason `belowSeam` is. */
  clubRuns: readonly ClubRun[]
  highlights: readonly Highlight[]
  elevation: ElevationProfile | null
  /** Closes the legend, which any tap that opens a sheet does. */
  onCloseLegend: () => void
}

export function useTappedLinePanel({
  spurs,
  pois,
  units,
  trailName,
  pace,
  walked,
  trailIndex,
  belowSeam,
  clubSections,
  clubRuns,
  highlights,
  elevation,
  onCloseLegend,
}: TappedLineInput): TappedLinePanel {
  /** The tapped trail line's published facts, or null (#134). The map
   *  reports them (map/lineTaps.ts); what they mean - the spur record, the
   *  destination's name - is resolved here, where the data is. */
  const [selectedLine, setSelectedLine] = useState<TappedLine | null>(null)
  const [selectedHighlightId, setSelectedHighlightId] = useState<string | null>(null)

  /**
   * The tapped line's sheet content (#134), resolved here for the reason
   * `selectedPoi` is: the map reports what was drawn, and the shell is what
   * holds the spur records, the POI a spur leads to, and the hiker's units.
   */
  const lineDetail: LineDetail | null = useMemo(() => {
    if (selectedLine === null) return null
    return buildLineDetail(selectedLine, spurs, pois, units, trailName, pace)
  }, [selectedLine, spurs, pois, units, trailName, pace])

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
          <LineSheet detail={lineDetail} onClose={() => setSelectedLine(null)} />
        ),
    }),
    [handleSelectLine, handleSelectHighlight, highlightDetail, clubDetail, lineDetail],
  )

  return { mapScreen }
}
