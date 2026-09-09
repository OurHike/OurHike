// A download-level choice, shared by the Downloads screen's cards and
// onboarding so the two can never drift apart.
//
// Options-driven since #276, because there are two sheets with two different
// level sets now: the USGS raster's Light/Standard/Fine tiers and the hiking
// sheet's Standard/Fine cuts. The options carry their real measured sizes -
// rendered through lib/formatBytes.ts rather than typed as copy - and the
// builders below are the only places each sheet's options are assembled, so
// a size shown anywhere is the same size shown everywhere.
//
// EVERY LEVEL, ALWAYS - GREYED WHERE IT IS NOT ON OFFER (#298).
//
// Two different level sets meant two differently-shaped pickers, and once
// the sheets sit under tabs (screens/Tabs.tsx) that difference is what a
// hiker actually sees when they switch: three rows become two, and the row
// that vanished is the cheapest one. A missing row cannot say whether this
// map has no Light version or whether the app forgot to ask. So the ladder
// is the same under every tab and a level a sheet does not have renders
// disabled, saying so.
//
// Disabled radios are deliberately still radios. A greyed row that is a
// `<span>` looks the same and reads as nothing at all; an input with
// `disabled` is announced as an unavailable option, which is the fact.
//
// The same greying carries a second, unrelated case: levels that exist but
// cannot be chosen right now, because bytes are already on the phone or on
// their way. `locked` is that one, and it comes with a note saying what
// would have to happen instead - see DownloadCard.
//
// AND A THIRD: A LEVEL THIS PHONE HAS NO ROOM FOR (#555).
//
// Every browser on iOS is WebKit, whose per-origin allowance starts around a
// gigabyte and prompts beyond it. The Fine raster tier is 1.18 GB, over that
// before the origin is holding anything else - and nothing in the download path
// branched on platform, so the rung was offered with a size and a radio button
// on a phone that could never store it.
//
// THE HIKING SHEET AT FINE NO LONGER IS, and the change is worth naming rather
// than quietly dropping: it was 1.14 GB when this was written, and the corridor
// taper (#1088) brought it to 809.5 MB. That does not make this check
// redundant - it is a reading of what the browser says is free, never a
// threshold anybody typed, so a phone already holding a raster tier still fails
// it. What changed is that the default sheet's own worst case now fits where it
// did not. #547 made the tap a truthful refusal in about 30 ms instead of a
// wasted transfer, which is a real improvement over spending someone's data and
// still worse than not offering a rung that cannot work.
//
// It gets its OWN sentence rather than reusing "Not offered", and the distinction
// is the point: "not offered" is a fact about the map, this is a fact about the
// phone, and a hiker who reads the wrong one goes looking for a different map
// instead of freeing up space. The size stays visible for the same reason - what
// it would cost is exactly what they need in order to decide what to delete.
//
// Never a platform check. The comparison is against what the browser reports as
// free (lib/useAvailableBytes.ts), so it is true on an Android phone with a full
// disk and false on an iPad with room - both of which a UA sniff gets wrong. An
// unknown allowance refuses nothing, which is dataSaver.ts's posture for an
// absent API.

import { DOWNLOAD_DETAIL_LEVELS, type DetailLevel } from '../lib/downloadDetail'
import { offeredHikingDetails } from '../lib/hikingDetail'
import {
  CORRIDOR_BACKGROUND_PACKAGE,
  hikingSheetSizeBytes,
  packageSizeBytes,
} from '../lib/packages'
import { NO_PUBLISHED_SIZES, type PublishedSizes } from '../lib/usePublishedSizes'
import { formatBytes } from '../lib/formatBytes'

export interface DetailOption {
  id: string
  label: string
  /**
   * What this download costs at this level, or null where nothing has
   * measured it.
   *
   * Null no longer means one thing, which is why `offered` exists beside it
   * (#1167). A rung can be unpriced because this sheet has no such level, or
   * because it has one and `latest.json` has not landed to say what it
   * weighs. Those read very differently to somebody choosing, so the row says
   * which - "Not offered" against "Unknown offline".
   */
  sizeBytes: number | null
  /**
   * Whether this level exists for this sheet and its artifacts are in the
   * bucket - hikingDetail.ts's `published` gate, the 404-on-a-mountain rule.
   *
   * Separate from having a size, because since #1167 an offered rung can be
   * unpriced. A rung that is not offered may never be chosen; a rung that is
   * offered but unpriced may.
   */
  offered: boolean
  recommended: boolean
}

/**
 * The rungs every picker shows, cheapest first.
 *
 * One ladder for both sheets, so switching tabs never reshuffles the rows.
 * It is the raster's own three because that is the widest set anything
 * offers; a sheet with fewer fills the gaps with nulls.
 */
const LEVEL_LADDER: ReadonlyArray<{ id: DetailLevel; label: string }> = [
  { id: 'light', label: 'Light' },
  { id: 'standard', label: 'Standard' },
  { id: 'fine', label: 'Fine' },
]

/** The USGS raster's tiers, sizes from downloadDetail.ts. Published at all
 *  three, so nothing here is greyed. */
export function rasterDetailOptions(
  published: PublishedSizes = NO_PUBLISHED_SIZES,
): DetailOption[] {
  return LEVEL_LADDER.map(({ id, label }) => {
    const detail = DOWNLOAD_DETAIL_LEVELS.find((level) => level.level === id)
    return {
      id,
      label,
      // Priced through the package rather than off the tier table, so the
      // bucket's own figure wins where latest.json carries one and the tier
      // table is the fallback (#505). Same resolution the hiking sheet gets
      // below - one path, so the two ladders cannot drift into disagreeing
      // about where a size comes from.
      sizeBytes:
        detail === undefined
          ? null
          : packageSizeBytes(CORRIDOR_BACKGROUND_PACKAGE, id, 'standard', published),
      // The raster's tiers are still priced from downloadDetail.ts, whose
      // build is withdrawn (#855), so `offered` and "has a size" still agree
      // here. Set from the level's existence rather than from the size so it
      // keeps meaning the same thing as the hiking ladder's below.
      offered: detail !== undefined,
      recommended: detail?.recommended ?? false,
    }
  })
}

/**
 * The hiking sheet's levels (#276). Each option's size is the WHOLE sheet at
 * that level - the basemap cut plus the DEM - because that is the number a
 * hiker weighs against their storage, not one archive's share of it.
 *
 * A level comes back UNOFFERED when the ladder has a rung this sheet has no
 * level for, or when the level exists in the catalog but its artifacts are not
 * in the bucket yet (hikingDetail.ts's `published`, the same 404-on-a-mountain
 * rule packages.ts's `source: null` enforces one level up). Light was the
 * second case between #1088, which named its artifacts, and #1107, which built
 * them. An unoffered rung is still drawn, greyed, rather than left out - see
 * the header.
 *
 * It comes back OFFERED WITH A NULL SIZE when `latest.json` has not landed:
 * since #1167 the manifest is the only thing that prices this sheet, so a
 * phone that has never reached it knows which levels exist and not what they
 * cost. That rung stays choosable - withholding the size is not withholding
 * the map.
 */
export function hikingDetailOptions(
  published: PublishedSizes = NO_PUBLISHED_SIZES,
): DetailOption[] {
  const offered = offeredHikingDetails()
  return LEVEL_LADDER.map(({ id, label }) => {
    const detail = offered.find((level) => level.level === id)
    return {
      id,
      label,
      sizeBytes:
        detail === undefined ? null : hikingSheetSizeBytes(detail.level, published),
      // Offered because `offeredHikingDetails()` returned it - its artifacts
      // are in the bucket. Whether the manifest has told this phone what they
      // weigh is a separate question since #1167, and the two answers are no
      // longer the same boolean.
      offered: detail !== undefined,
      recommended: detail?.recommended ?? false,
    }
  })
}

/**
 * The ladder with nothing behind any rung - what a sheet gets before anyone
 * has wired it a level set.
 *
 * A sheet with no dial used to render no picker, which under tabs is the
 * ambiguity this change exists to remove. Three greyed rows say "no levels
 * published for this map" out loud, and a new sheet that reaches a screen
 * before its options do says something true rather than nothing.
 */
export function noDetailOptions(): DetailOption[] {
  return LEVEL_LADDER.map(({ id, label }) => ({
    id,
    label,
    sizeBytes: null,
    offered: false,
    recommended: false,
  }))
}

export interface DetailPickerProps {
  options: readonly DetailOption[]
  value: string
  onChange: (id: string) => void
  /** Every level greyed because no choice can be taken here at all - bytes
   *  already on the phone or on their way, or a screen that is showing this
   *  sheet rather than configuring it. `lockedNote` says which. */
  locked?: boolean
  lockedNote?: string
  /** Distinguishes the radio group when two pickers share a page - and two
   *  do, now that both sheets' cards carry one. */
  name?: string
  /**
   * What the browser says this origin can still store, or null where it will
   * not say (lib/useAvailableBytes.ts).
   *
   * Null offers everything. It means "unknown", and a level greyed out on an
   * unknown allowance would be a claim about the phone that nothing supports -
   * the same reason Downloads.tsx warns rather than refuses on a tight estimate.
   */
  availableBytes?: number | null
}

export function DetailPicker({
  options,
  value,
  onChange,
  locked = false,
  lockedNote,
  name = 'map-detail',
  availableBytes = null,
}: DetailPickerProps) {
  return (
    <fieldset className="detail-picker">
      <legend className="detail-picker__legend">Map detail</legend>

      {options.map((option) => {
        const offered = option.offered
        // Published, and larger than the phone says it can hold. Deliberately
        // not folded into `offered`: the two read differently to a hiker and the
        // rung says which.
        const noRoom =
          option.sizeBytes !== null &&
          availableBytes !== null &&
          option.sizeBytes > availableBytes
        const disabled = locked || !offered || noRoom

        return (
          <label
            key={option.id}
            className="detail-picker__option"
            data-disabled={disabled}
          >
            <input
              type="radio"
              name={name}
              value={option.id}
              // Never pre-selected where the level does not exist: a checked
              // "Light" on a sheet that has no Light cut would state a size
              // this download is not. A level the phone has no room for stays
              // shown as chosen if it already was - the preference is the
              // hiker's, and silently re-pointing it at a smaller map would
              // change what they asked for without telling them.
              checked={offered && value === option.id}
              disabled={disabled}
              onChange={() => onChange(option.id)}
            />
            <span className="detail-picker__name">{option.label}</span>
            <span className="detail-picker__size">
              {/* Three answers, never two. An offered rung with no size is
                  not "Not offered" - it is a level a hiker may take whose
                  cost this phone has not been told yet, and saying the wrong
                  one of those would either hide a real choice or invent a
                  size (#1167). */}
              {option.sizeBytes !== null
                ? formatBytes(option.sizeBytes)
                : offered
                  ? 'Unknown offline'
                  : 'Not offered'}
            </span>
            {noRoom && (
              // Names the phone, not the map, and stays beside the size rather
              // than replacing it: what it would cost is what a hiker needs in
              // order to decide what to free up.
              <span className="detail-picker__no-room">No room on this phone</span>
            )}
            {option.recommended && offered && !noRoom && (
              <span className="detail-picker__recommended">Recommended</span>
            )}
          </label>
        )
      })}

      {locked && lockedNote !== undefined && (
        <p className="detail-picker__note">{lockedNote}</p>
      )}
    </fieldset>
  )
}
