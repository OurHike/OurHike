// Legend contents: what's in the current viewport, with counts. See
// WIREFRAMES.md's Legend section - recomputed fresh per viewport (no
// caching/staleness here, that's the whole point of a legend that reflects
// "what's on screen right now"), and rows are tappable to hide except
// closure/serious-warning, which carry no per-category switch at all per Map
// Options/Hiker Safety. That used to be stated as "never a hideable safety
// layer, anywhere in the app"; #1047 narrowed it to what this file can
// actually enforce, and NEVER_HIDEABLE below carries the whole of it.
//
// One row per category. The confidence split this used to carry, and why it
// went, is on LegendRow.
//
// AND WHAT IS DRAWN, WHERE THAT IS FEWER (#528).
//
// "What am I looking at right now" is the promise, and since collision culling
// arrived this had quietly been answering "what is inside this rectangle"
// instead. `icon-allow-overlap: false` means MapLibre draws no two colliding
// pins, so at hiking zooms a row can read `Privy 6` on a map with no privy pin
// on it - 3% of privies place at z14, measured. A count that is structurally
// unable to be wrong about presence and silently wrong about visibility is the
// more dangerous of the two.
//
// So a row carries the drawn count too, where it differs, and map/drawnPois.ts
// supplies it from what MapLibre actually placed. Per-row rather than as a
// single headline total, and deliberately: a "38 of 112 fit" line averages away
// the only rows that are alarming, which are the ones at or near zero.
//
// AND EVERY OTHER CATEGORY BELOW THEM, BECAUSE THE ROWS ARE ALSO THE TOGGLES
// (#723). That job wants the whole list and this one wants the viewport, so they
// are two functions rather than one: `computeLegendContents` still answers only
// what is in the rectangle, and `withEveryType` pads it for the grid alone.
//
// AND THE TWO SAFETY SYMBOLS, NAMED RATHER THAN COUNTED (#1051). `withSafetyKey`
// appends a closure row and a serious-warning row to that same grid. They are
// the only rows here that carry no count, because neither layer is a `MapPoint`
// this file could count or a pin map/drawnPois.ts could measure - so what they
// offer is a key entry, which is the thing that was actually missing.

export interface BoundingBox {
  west: number
  south: number
  east: number
  north: number
}

export interface MapPoint {
  id: string
  type: string
  lat: number
  lon: number
  confidence: 'high' | 'low'
  /**
   * The waypoint's name, for map/poiLabels.ts (#1194).
   *
   * Optional, and nothing in THIS file reads it - the legend counts
   * categories. It rides here for the same reason `siteId` does: the shell
   * already maps a `StoredPoi` onto this type once, and a parallel array of
   * names would be a second thing to keep in step. Absent means the caller
   * had no name to give, and the label layer draws nothing rather than
   * "Unnamed" - lib/trailData.ts's own restraint, one layer out.
   */
  name?: string
  /**
   * Which site this point belongs to, and whether it anchors it (#523/#524).
   *
   * Here rather than in a parallel type because the shell already maps a stored
   * POI onto this once, and a second array to keep in step with it is a second
   * thing that can fall out of step. Nothing in THIS file reads them - the
   * legend counts what is in the viewport, and a privy riding a shelter pin is
   * still a privy in the viewport, which is deliberate: hiding it from the count
   * would make the panel disagree with the data for the sake of agreeing with
   * the pins. map/poiSites.ts is what reads them.
   */
  siteId?: string
  siteRole?: string
}

/**
 * One row per category, and deliberately NOT one per category per confidence.
 *
 * It used to split: "Water 2" and "Water · Unverified 1" were two rows. That
 * doubled the length of a panel whose 2-column grid is about 116px wide beside
 * a desktop map, so half the labels wrapped onto a second line, and it spent
 * that room on a distinction a hiker cannot act on from here - the count is
 * "what is around me", and which particular spring is unconfirmed is a
 * question about one spring. The map still says it per pin (a broken rim), and
 * the waypoint card still says it in words, which is where somebody deciding
 * whether to walk to it is actually looking (chrome/PoiCard.tsx).
 */
export interface LegendRow {
  type: string
  /**
   * How many of this category are in the viewport, or undefined on a row that
   * NAMES a symbol rather than counting it (#1051).
   *
   * Undefined is the two safety rows and only them. `withSafetyKey` appends a
   * closure row and a serious-warning row to the grid, and neither can honestly
   * carry a number: a closure reaches the shell as a mile-marker range and
   * becomes a `ClosureBand`, a serious warning as a moderated report and becomes
   * a `WarningPoint`, and neither is ever a `MapPoint` for `computeLegendContents`
   * to count. Nothing in map/drawnPois.ts measures either one, so a count on
   * these rows would be a figure with no measurement behind it, on the panel
   * whose whole promise is that its figures are about the screen.
   *
   * A row WITH a count is a row `legendDropSummary` is entitled to reason about;
   * a row without one is a key entry and nothing else.
   */
  count?: number
  hideable: boolean
  /**
   * How many of `count` the map actually drew, or undefined where nobody
   * measured.
   *
   * Undefined and zero are different answers and must stay so: the pin layer is
   * absent on a cold start, and rendering "0 shown" then would claim a drop that
   * has not happened. Undefined renders as the plain count, exactly as this did
   * before #528.
   */
  drawnCount?: number
}

/**
 * The two safety layers, in the order the legend grid draws them (#1051).
 *
 * An array rather than only the Set below because the grid needs an ORDER and
 * `NEVER_HIDEABLE` is asked a different question - "may a stored preference
 * reach this?" - by four call sites that do not care what order anything is in.
 * One list, two shapes, and the Set is built from this so they cannot drift:
 * a third layer added here is hideable by nobody and drawn on the key, without
 * a second edit that somebody has to remember.
 */
export const SAFETY_LAYERS = ['closure', 'serious-warning'] as const

/**
 * The one guard on the safety layers, exported so lib/waypointVisibility.ts
 * filters every stored preference through the SAME set rather than a second
 * copy of it (#530).
 *
 * WHAT THIS SET STILL PROMISES, NARROWED BY #1047. It used to be the whole of
 * "closures and serious warnings have no hide affordance anywhere in the app".
 * The legend now carries an Alerts switch that takes those marks off the
 * canvas, so the sentence is no longer true as written - and the half that
 * matters is the half this set is actually able to enforce.
 *
 * The promise now: **no STORED value can produce a map with a closure hidden
 * on it.** Not a hand-edited preference, not one synced from an older client,
 * not "only water", not a category a later release adds. That is what every
 * function in lib/waypointVisibility.ts filtering through this set buys, and
 * it is exactly the failure the maintainer's constraint on #1047 names - a
 * thru-hiker whose phone opens with the alerts already off, for days, having
 * chosen it once.
 *
 * What is no longer promised is permanence within a single view. The Alerts
 * switch is deliberately not routed through here or through
 * `waypoint_types_shown` at all: it is a `useState` in
 * chrome/alertLayerPanel.ts that nothing writes down, and it resets whenever
 * the app is next opened. Two mechanisms, and the reason they are two is that
 * only one of them can outlive the moment a hiker is looking at the screen.
 *
 * features/MAP_OPTIONS.md §"Reroutes / closures" and features/HIKER_SAFETY.md
 * carry the decision.
 */
export const NEVER_HIDEABLE: ReadonlySet<string> = new Set<string>(SAFETY_LAYERS)

function isWithin(point: MapPoint, bbox: BoundingBox): boolean {
  return (
    point.lon >= bbox.west &&
    point.lon <= bbox.east &&
    point.lat >= bbox.south &&
    point.lat <= bbox.north
  )
}

/**
 * @param verifiedOnly The legend's "Verified?" toggle. Unverified points are
 *   left out of the COUNTS as well as off the map, because the whole promise
 *   of this panel is that it says what is on screen right now: a row reading
 *   "Water 3" over a map drawing two would be the panel telling the exact lie
 *   it exists to prevent.
 * @param drawn How many of each category MapLibre actually placed
 *   (map/drawnPois.ts), keyed by type alone so it joins these rows without a
 *   translation step. Omitted where nobody measured.
 */
export function computeLegendContents(
  bbox: BoundingBox,
  points: MapPoint[],
  verifiedOnly = false,
  drawn?: ReadonlyMap<string, number>,
): LegendRow[] {
  const counts = new Map<string, number>()

  for (const point of points) {
    if (!isWithin(point, bbox)) continue
    // Never a safety layer, whatever the toggle says. A closure nobody has
    // confirmed is still a closure, and a filter that happens to take one off
    // the panel is the same failure as a button that does, and easier to ship
    // by accident. The map agrees structurally: closures and warnings are their
    // own layers, so poiFilter() cannot reach them either.
    //
    // Untouched by #1047's Alerts switch, and deliberately: that flag is not a
    // filter and is not stored, so it has no business arriving here. What a
    // panel SAYS is in the rectangle stays a fact about the rectangle.
    if (verifiedOnly && point.confidence !== 'high' && !NEVER_HIDEABLE.has(point.type))
      continue
    // Keyed by type alone, so a verified and an unverified spring are two
    // springs rather than two rows - see LegendRow.
    counts.set(point.type, (counts.get(point.type) ?? 0) + 1)
  }

  return Array.from(counts.entries()).map(([type, count]) => ({
    type,
    count,
    hideable: !NEVER_HIDEABLE.has(type),
    // Absent from the measurement means none of this category was placed, which
    // is 0 rather than unmeasured - the whole map was measured, so a missing key
    // is an answer. `drawn` being absent entirely is the unmeasured case, and
    // then no row carries a figure at all.
    //
    // Clamped to the present count: a drawn figure larger than the rectangle
    // holds can only be a duplicate the probe failed to fold (see
    // map/drawnPois.ts), and `Water 14 · 17 shown` would discredit every other
    // row on the panel. The clamp also covers the `verifiedOnly` case, where the
    // counts above exclude unverified points and the map has filtered them out
    // too, so the two agree by construction rather than by coincidence.
    drawnCount: drawn === undefined ? undefined : Math.min(drawn.get(type) ?? 0, count),
  }))
}

/**
 * The same rows, with a zero row for every category `types` names and the
 * viewport does not hold (#723).
 *
 * WHY THIS EXISTS. `computeLegendContents` answers "what is in this rectangle",
 * and the rows are also the hide toggles - so at the zooms a hiker reads a place
 * from, the panel carrying the toggles carries two of them. That is arithmetic,
 * not a rare case: features/POI_VISIBILITY.md's own density table puts 2-4
 * waypoints in a 390 x 700 phone map at z14 and 4-8 at z13. A category with
 * nothing in view had no row and could not be switched from this panel at all,
 * which chrome/Legend.tsx has named in a comment since #530 without fixing.
 *
 * SEPARATE FROM `computeLegendContents` ON PURPOSE. That function is what
 * chrome/MapScreen.tsx feeds `legendDropSummary` for the count over the canvas,
 * and what the panel's own "nothing here yet" and "turn Verified? off" sentences
 * are decided by. All three speak about the viewport, and padding at the source
 * would have them speaking about the category list instead. Only the grid is
 * padded, and only where it is rendered.
 *
 * @param types The categories to guarantee a row for - in practice
 *   lib/waypointVisibility.ts's `HIDEABLE_TYPES`, passed in rather than imported
 *   because that module imports `NEVER_HIDEABLE` from this one. It is also the
 *   ORDER the padded rows come back in, which is a second thing worth having:
 *   `computeLegendContents` returns whatever order the points happened to be
 *   encountered in, so the grid re-shuffled itself as a hiker panned.
 *
 *   A row already present keeps its count, its `drawnCount` and its
 *   `hideable` flag untouched. Rows whose type is not in `types` - the safety
 *   layers, which have no toggle to reach and no business claiming "Closure 0"
 *   on a stretch with no closure on it - are appended in their original order
 *   rather than padded. What gives those two a row of their own is
 *   `withSafetyKey` below, which appends a key entry carrying no count at all:
 *   the objection above is to the NUMBER, and it is why they still have none.
 */
export function withEveryType(
  rows: readonly LegendRow[],
  types: readonly string[],
): LegendRow[] {
  const byType = new Map(rows.map((row) => [row.type, row]))

  const listed = types.map(
    (type) =>
      byType.get(type) ?? {
        type,
        count: 0,
        // Every type this is called with is hideable by construction - the
        // caller's list excludes the safety layers. Read from NEVER_HIDEABLE
        // anyway, so a caller passing a wider list cannot manufacture a toggle
        // for a closure by handing this the wrong array.
        hideable: !NEVER_HIDEABLE.has(type),
        // NOT zero. `drawnCount` reports a DROP - how many of the ones here did
        // not fit - and there is no drop to report on a category with nothing
        // here. Zero would put this row into `legendDropSummary`'s arithmetic as
        // a measured row, and render the count as a plain `0` either way.
        drawnCount: undefined,
      },
  )

  const known = new Set(types)
  return [...listed, ...rows.filter((row) => !known.has(row.type))]
}

/**
 * The same rows, with a key entry for each safety layer (#1051).
 *
 * WHY THOSE ROWS WERE NEVER ON THE PANEL. `computeLegendContents` counts
 * `MapPoint`s, and the shell builds those from `pois` alone - the eight
 * artifact-backed categories in `POI_TYPES`. A closure arrives from the backend
 * as a mile-marker range and becomes a `ClosureBand`; a serious warning arrives
 * as a moderated report and becomes a `WarningPoint`. Neither is ever a
 * `MapPoint`, and neither could be. `withEveryType` could not save them either -
 * it pads from `HIDEABLE_TYPES`, which is `POI_TYPES` minus exactly these two.
 * So the rows below, their icons and their tag rendered only in
 * chrome/Legend.test.tsx, and the legend - the only key this app has - has never
 * named the barred red band across the trail or the red triangle pin bigger than
 * every other mark on the map. Tapping one does answer, and "tap the thing you
 * do not recognise" is a worse instruction for a hazard than for a spring.
 *
 * A KEY ENTRY RATHER THAN A COUNT, which is the decision and not a shortcut.
 * These rows carry an icon, a name and their tag, and no number in any state.
 * Two reasons, and the second is the one that would bite:
 *
 *  - Nobody measures either layer. `map/drawnPois.ts` measures the PIN layers,
 *    and a closure is a line while `map/warningLayers.ts` sets
 *    `icon-allow-overlap: true` on the warning pin on purpose. A count here
 *    would be a figure with no measurement behind it on the one panel whose
 *    promise is that its figures are about the screen.
 *  - A counted safety row lands in `legendDropSummary`'s arithmetic carrying
 *    `drawnCount: 0` against a real count, and the panel announces that none of
 *    the closures on screen fit - about the one category that is always drawn.
 *    That summary now excludes uncounted rows explicitly (see below), so this is
 *    belt and braces rather than the only guard, but the row still has no honest
 *    number to print.
 *
 * A real viewport count is the other shape #1051 weighs, and it is a bigger
 * change than this one: the shell would have to project `ClosureBand` geometry
 * and `WarningPoint` coordinates against the bbox, which nothing does today.
 *
 * ALWAYS PRESENT, WHICH IS THE POINT AND IS A REVERSAL. `withEveryType` appends
 * a safety row only where the viewport put one there, on the reasoning that
 * "Closure 0" is a claim about closures that nothing asked this panel to make.
 * That reasoning is about a COUNT, and it is right about counts - it is why
 * these rows carry none. A key entry makes no claim about the rectangle at all:
 * it says what the symbol means, which is the gap, and a key that appears only
 * once you are already looking at the thing you did not recognise is not a key.
 *
 * Any counted safety row the caller happens to hold is replaced rather than
 * kept, so the row means one thing rather than changing shape with whatever the
 * shell fed it. Only chrome/Legend.test.tsx feeds one today.
 *
 * THE GRID ALONE, like `withEveryType` above it. Every SENTENCE on the panel is
 * decided by `computeLegendContents`'s rows, and none of them may start speaking
 * for a category the viewport does not hold.
 */
export function withSafetyKey(rows: readonly LegendRow[]): LegendRow[] {
  const keyed: LegendRow[] = SAFETY_LAYERS.map((type) => ({
    type,
    // No count and no drawn figure: a key entry names a symbol, and both of
    // those fields are answers about a rectangle. See LegendRow.count.
    count: undefined,
    drawnCount: undefined,
    // Read as a fact rather than written as one, so this cannot become the
    // place a safety layer quietly acquires a toggle.
    hideable: !NEVER_HIDEABLE.has(type),
  }))

  return [...rows.filter((row) => !NEVER_HIDEABLE.has(row.type)), ...keyed]
}

/**
 * What to say at the head of the panel: how many waypoints are in view against
 * how many fit, or null when there is nothing to report.
 *
 * Null in three cases, and they are all "say nothing": nothing measured, nothing
 * present, or everything present is drawn. A line reading "112 of 112 fit" is
 * noise on a panel someone opens all day to answer a different question.
 *
 * The summary, not the point - see the header comment. It exists because "is
 * there anything here I am not being shown" should be answerable without reading
 * every row, and it is deliberately second-order: the rows are where a hiker
 * learns that the missing category is the privies.
 *
 * A HIDDEN CATEGORY IS IN NEITHER HALF OF THE FRACTION (#777). Its absence from
 * the map is the hiker's own filter, not the camera, and the remedy this line
 * prescribes - zoom in - cannot cure it. Counted as present, "only shelters"
 * over a busy stretch read "5 of 42 fit" with the 37 the filter removed, and
 * because the drawn measurement already reflects the filter (map/drawnPois.ts
 * queries what MapLibre placed), `drawn < present` held at every camera - the
 * line never left the screen while a filter was on. The per-row fractions are
 * untouched: a greyed-out row reading `0/14` is that row saying what
 * re-enabling it would buy.
 *
 * @param hiddenTypes The legend's hidden set. Read through NEVER_HIDEABLE like
 *   every consumer of the preference (lib/waypointVisibility.ts), so no
 *   caller's set can quiet this summary about a safety layer.
 */
export function legendDropSummary(
  rows: readonly LegendRow[],
  hiddenTypes?: ReadonlySet<string>,
): { present: number; drawn: number } | null {
  const hidden = (row: LegendRow) =>
    hiddenTypes !== undefined &&
    hiddenTypes.has(row.type) &&
    !NEVER_HIDEABLE.has(row.type)
  // UNCOUNTED ROWS ARE OUT, SAID RATHER THAN IMPLIED (#1051). A key entry
  // carries no count and no drawn figure, so `drawnCount !== undefined` already
  // drops it and this line changes no arithmetic today. It is here because the
  // accident is what #1051 warned about: the reason a safety row must never
  // reach this sum is that nobody MEASURES those layers, and a future row that
  // acquires a count while staying unmeasured would slip in through a guard
  // that was only ever about `drawnCount`. Both halves of "counted and
  // measured" are now asked for by name.
  const measured = rows.filter(
    (row) => row.drawnCount !== undefined && row.count !== undefined && !hidden(row),
  )
  if (measured.length === 0) return null

  const present = measured.reduce((total, row) => total + (row.count ?? 0), 0)
  const drawn = measured.reduce((total, row) => total + (row.drawnCount ?? 0), 0)
  return present > 0 && drawn < present ? { present, drawn } : null
}

/**
 * The one sentence the legend gains when the map is drawing more than one
 * system's trails (#783, features/NEARBY_TRAILS.md §1).
 *
 * A SENTENCE OF STATE, AND DELIBERATELY NOT A CONTROL. The doc's reasoning,
 * kept because it is the whole decision: "nothing here is hideable: nearby
 * trails are context, and context that can be switched off is a mode nobody
 * remembers being in." The second clause is what stops a hiker hunting the
 * legend for the toggle the first clause implies - a legend that explains a
 * dimming without saying it is permanent reads as a control that has gone
 * missing.
 *
 * Shown only while a ghosted trail is actually on screen (map/drawnBlazes.ts's
 * drawsNearbyTrails). On an A.T.-only download nothing is dimmed, and a
 * sentence explaining a distinction the map is not drawing is a sentence about
 * nothing.
 */
export const GHOSTED_TRAILS_NOTE =
  'Other trails are dimmed; the trail you chose is full-strength. Nothing here turns them off.'
