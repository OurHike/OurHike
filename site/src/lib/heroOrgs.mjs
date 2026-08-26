// The data behind the homepage hero's rotation (site/src/pages/index.astro,
// #1059/#1060) - split out of the page itself so the one claim that actually
// matters ("every organization here shows up in the rotation") is something
// a test can check directly, rather than something only a human reading the
// Astro file and the rendered page side by side could verify.
//
// Every organization whose trail/path LINE geometry OurHike ships to a
// hiker's phone today - not water points, not conditions, not photo
// credit-only sources. Read from pipeline/sources.json 2026-08-26: the
// `reaches_hikers: true` entries whose export carries trail geometry rather
// than points - `centerline` + `side_trails` (ATC), `oprhp_trails`,
// `nynjtc_long_path` + `nynjtc_highlands_trail` (one organization, two
// layers), `mohonk_trails`, `dec_hiking_trails`. Update this list if that
// roster changes - heroOrgs.test.mjs is what notices if the count line or
// the rotation itself falls out of step with it.
//
// Each carries two candidate lines rather than one - both written, both
// shipped, rather than picking a favorite - so the rotation still varies
// even while sitting on one organization's turn.
//
// `lat`/`lon` are each organization's approximate headquarters or main
// office, from public knowledge rather than a geocoder - not surveyed, never
// rendered, and used for exactly one thing client-side: a rough sort of
// these organizations by estimated distance from the visitor. Precision here
// would be spurious - the point is "which club is roughly closest", not a
// real distance.
export const ORGS = [
  {
    lines: [
      'The whole Appalachian Trail, offline.',
      '2,197 miles of Appalachian Trail. Zero bars required.',
    ],
    lat: 39.3253,
    lon: -77.7386, // ATC, Harpers Ferry, WV
  },
  {
    lines: [
      'Every step of the volunteer-maintained NY-NJ Trail Conference, right in your pocket.',
      'All bazillion NY-NJ Trail Conference blazes, yours to download.',
    ],
    lat: 41.0898,
    lon: -74.1447, // NYNJTC, Mahwah, NJ
  },
  {
    lines: [
      'Every trail NY State Parks maintains, offline in your pocket.',
      'All of NY State Parks’ trails. None of the parking-lot wifi.',
    ],
    lat: 42.6525,
    lon: -73.7572, // NYS OPRHP, Albany, NY
  },
  {
    lines: [
      'The Shawangunks’ cliffs and carriage roads, mapped by Mohonk Preserve.',
      'Mohonk Preserve’s trails, minus the gift-shop line.',
    ],
    lat: 41.7626,
    lon: -74.1071, // Mohonk Preserve, Gardiner, NY
  },
  {
    lines: [
      'Catskills to Adirondacks: every trail NYS DEC blazes.',
      'All of DEC’s hiking trails, no ranger station required.',
    ],
    lat: 42.6551,
    lon: -73.7472, // NYS DEC, Albany, NY
  },
]

/** "N organizations sharing all their trails and paths" - always the count
 *  of whatever `orgs` list is passed, never a hand-typed number, so this
 *  cannot go stale the way the credits strings elsewhere on the site did
 *  before #1059. */
export function orgCountLine(orgs = ORGS) {
  return `${orgs.length} organizations sharing all their trails and paths`
}

/** The full rotation: the count line first, then every organization's lines
 *  in list order. What site/src/pages/index.astro's inline script re-derives
 *  client-side (there, to re-sort by estimated distance first) - kept here
 *  as the one place that says what "every organization's lines are in the
 *  rotation" actually means, so a test can hold the page to it. */
export function allSlides(orgs = ORGS) {
  return [orgCountLine(orgs)].concat(orgs.flatMap((org) => org.lines))
}
