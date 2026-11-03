// The homepage hero's rotation (site/src/pages/index.astro, #1059/#1060):
// a count line, then lines about the organizations whose data the map
// carries - split out of the page so a test can hold the rotation to what it
// claims without rendering the page.
//
// ORGS IS NOT THE ROSTER. Until #1877 it was: the five organizations whose
// trail/path LINE geometry OurHike shipped on 2026-08-26, typed in by hand,
// and the count line counted them while the registry grew to 150. The roster
// is now orgRoster.mjs, read from pipeline/sources.json at build time, and
// the count line counts that. What lives here is the copy only a person can
// write. The maintainer asked for it on 2026-10-23 - "keep the whimsy on the
// first page that rotates. Go find some fun things to say" - and the lines
// for everyone past the first five were written then.
//
// EVERY LINE IS ABOUT DATA THAT SHIPS. Each was written against that
// organization's `reaches_hikers: true` source titles in sources.json on
// main at 072fc298 - "privies and all" because the Green Mountain Club ships
// a Long Trail privies layer, "44 passages" because the Arizona Trail
// Association's layer is titled with them. The jokes are about things the
// data plainly does not hold (pancakes, trail magic, rain jackets), never
// about what it does. Lines that would have promised water - the GATC and
// OpenStreetMap water sources - were not written, and the Maah Daah Hey's
// line names its trailheads and crossings and not the water cache boxes its
// guide also lists: water is one of the four ways this app can hurt somebody
// (CLAUDE.md), and a slogan is the wrong voice for it. Mileages are the trails' own published figures or absent.
//
// `name` is the organization's name in sources.json's `organizations` block,
// exactly. rotationOrgs() drops any entry whose organization ships nothing, so
// an organization whose data stops shipping loses its line at the next build
// rather than keeping a claim nobody stands behind; heroOrgs.test.mjs fails
// on the same mismatch in the committed registry, so a typo cannot hide.
//
// Each carries one or two lines; two where both were worth keeping, so the
// rotation still varies while sitting on one organization's turn.
//
// `lat`/`lon` are approximate, from public knowledge rather than a geocoder:
// the organization's office, or for a line about one park or trail town, that
// place. Never rendered, and used for exactly one thing client-side: a rough
// sort by estimated distance from the visitor, so the lines a visitor sees
// first are about trails near them. Precision here would be spurious - the
// point is "which club is roughly closest", not a real distance.
import { shipping } from "./orgRoster.mjs";

export const ORGS = [
  {
    name: "Appalachian Trail Conservancy",
    lines: [
      "The whole Appalachian Trail, offline.",
      "2,197 miles of Appalachian Trail. Zero bars required.",
    ],
    lat: 39.3253,
    lon: -77.7386, // Harpers Ferry, WV
  },
  {
    name: "New York-New Jersey Trail Conference",
    lines: [
      "Every step of the volunteer-maintained NY-NJ Trail Conference, right in your pocket.",
      "All bazillion NY-NJ Trail Conference blazes, yours to download.",
    ],
    lat: 41.0898,
    lon: -74.1447, // Mahwah, NJ
  },
  {
    name: "New York State Office of Parks, Recreation and Historic Preservation",
    lines: [
      "Every trail NY State Parks maintains, offline in your pocket.",
      "All of NY State Parks’ trails. None of the parking-lot wifi.",
    ],
    lat: 42.6525,
    lon: -73.7572, // Albany, NY
  },
  {
    name: "Mohonk Preserve",
    lines: [
      "The Shawangunks’ cliffs and carriage roads, mapped by Mohonk Preserve.",
      "Mohonk Preserve’s trails, minus the gift-shop line.",
    ],
    lat: 41.7626,
    lon: -74.1071, // Gardiner, NY
  },
  {
    name: "New York State Department of Environmental Conservation",
    lines: [
      "Catskills to Adirondacks: every trail NYS DEC blazes.",
      "All of DEC’s hiking trails, no ranger station required.",
    ],
    lat: 42.6551,
    lon: -73.7472, // Albany, NY
  },
  {
    name: "Pacific Crest Trail Association",
    lines: [
      "The Pacific Crest Trail, Mexico to Canada, in airplane mode.",
      "PCT campsites and trailheads. Trail magic not included.",
    ],
    lat: 38.58,
    lon: -121.49, // Sacramento, CA
  },
  {
    name: "Continental Divide Trail Coalition",
    lines: [
      "The Continental Divide Trail, reroutes and closures included.",
      "Mexico to Canada along the Divide. Signal optional.",
    ],
    lat: 39.76,
    lon: -105.22, // Golden, CO
  },
  {
    name: "Arizona Trail Association",
    lines: ["All 44 passages of the Arizona Trail, Mexico to Utah."],
    lat: 32.22,
    lon: -110.97, // Tucson, AZ
  },
  {
    name: "Wisconsin Department of Natural Resources",
    lines: ["The Ice Age Trail, traced along where the glaciers finally gave up."],
    lat: 43.07,
    lon: -89.4, // Madison, WI
  },
  {
    name: "Ice Age Trail Alliance",
    lines: ["Ice Age Trail camping and parking, from the Alliance that tends it."],
    lat: 43.11,
    lon: -89.66, // Cross Plains, WI
  },
  {
    name: "North Country Trail Association",
    lines: ["The North Country Trail across eight states, offline the whole way."],
    lat: 42.93,
    lon: -85.34, // Lowell, MI
  },
  {
    name: "Florida Trail Association",
    lines: ["Florida Trail trailheads and trail towns. Bring bug spray, not a signal."],
    lat: 29.65,
    lon: -82.32, // Gainesville, FL
  },
  {
    name: "Green Mountain Club",
    lines: [
      "Vermont’s Long Trail, privies and all.",
      "The Long Trail’s places to sleep, summits and vistas, from the club that built it.",
    ],
    lat: 44.37,
    lon: -72.72, // Waterbury Center, VT
  },
  {
    name: "Appalachian Mountain Club",
    lines: ["AMC’s White Mountain huts and trailheads. Hut pancakes not included."],
    lat: 42.36,
    lon: -71.06, // Boston, MA
  },
  {
    name: "Tahoe Rim Trail Association",
    lines: ["The Tahoe Rim Trail, all the way around the lake."],
    lat: 38.96,
    lon: -119.94, // Lake Tahoe's south shore
  },
  {
    name: "Finger Lakes Trail Conference",
    lines: ["The Finger Lakes Trail, hunting-season bypasses included."],
    lat: 42.73,
    lon: -77.87, // Mount Morris, NY
  },
  {
    name: "Cumberland Trail Conference",
    lines: ["The Cumberland Trail along the plateau’s edge, campsites included."],
    lat: 35.95,
    lon: -85.03, // Crossville, TN
  },
  {
    name: "Friends of the Ouachita Trail",
    lines: ["The Ouachita Trail’s shelters, from the Friends’ own list."],
    lat: 34.75,
    lon: -92.29, // Little Rock, AR
  },
  {
    name: "Maah Daah Hey Trail Association",
    lines: ["The Maah Daah Hey’s trailheads, campgrounds and river crossings, in the Badlands."],
    lat: 46.91,
    lon: -103.52, // Medora, ND
  },
  {
    name: "Ozark Highlands Trail Association",
    lines: ["All five sections of the Ozark Highlands Trail, offline."],
    lat: 36.06,
    lon: -94.16, // Fayetteville, AR
  },
  {
    name: "Palmetto Conservation Foundation",
    lines: ["The Palmetto Trail, passage by passage, from the mountains to the sea."],
    lat: 34.0,
    lon: -81.03, // Columbia, SC
  },
  {
    name: "North Carolina Division of Parks and Recreation",
    lines: ["North Carolina’s Mountains-to-Sea Trail, from the Smokies to the Outer Banks."],
    lat: 35.78,
    lon: -78.64, // Raleigh, NC
  },
  {
    name: "City of Duluth",
    lines: ["The Superior Hiking Trail through Duluth, and the city parks it strings together."],
    lat: 46.79,
    lon: -92.1, // Duluth, MN
  },
  {
    name: "Lake County, Minnesota",
    lines: ["The Superior Hiking Trail along Lake Superior’s North Shore."],
    lat: 47.02,
    lon: -91.67, // Two Harbors, MN
  },
  {
    name: "Colorado Parks and Wildlife",
    lines: ["Colorado’s trails statewide, and the seasonal closures that give wildlife room."],
    lat: 39.74,
    lon: -104.99, // Denver, CO
  },
  {
    name: "Utah Geospatial Resource Center",
    lines: ["Utah’s trails and trailheads, statewide, red rock included."],
    lat: 40.76,
    lon: -111.89, // Salt Lake City, UT
  },
  {
    name: "Washington Recreation and Conservation Office",
    lines: ["Washington’s state trails database. Rain jacket not included."],
    lat: 47.04,
    lon: -122.9, // Olympia, WA
  },
  {
    name: "Mountains to Sound Greenway Trust",
    lines: ["The Mountains to Sound Greenway, from Seattle’s waterfront over the Cascades."],
    lat: 47.6,
    lon: -122.33, // Seattle, WA
  },
  {
    name: "Forest Park Conservancy",
    lines: ["Forest Park’s trailheads: a whole forest inside Portland."],
    lat: 45.57,
    lon: -122.77, // Forest Park, Portland, OR
  },
  {
    name: "Bay Area Ridge Trail Council",
    lines: ["Places to camp along the Bay Area Ridge Trail. The fog brings itself."],
    lat: 37.79,
    lon: -122.4, // San Francisco, CA
  },
  {
    name: "Alaska Trails",
    lines: ["The Alaska Long Trail’s cabins, campsites and crossings. Offline suits Alaska."],
    lat: 61.22,
    lon: -149.9, // Anchorage, AK
  },
  {
    name: "Black Hills Trails",
    lines: ["Sturgis trailheads, for when you came for the hiking, not the rally."],
    lat: 44.41,
    lon: -103.51, // Sturgis, SD
  },
  {
    name: "Texas Parks and Wildlife Department",
    lines: ["Texas State Parks’ trails, from the Panhandle to the Gulf."],
    lat: 30.27,
    lon: -97.74, // Austin, TX
  },
  {
    name: "Tennessee Department of Environment and Conservation",
    lines: ["Tennessee State Parks’ trails, campsites and closures, offline."],
    lat: 36.16,
    lon: -86.78, // Nashville, TN
  },
  {
    name: "National Park Service",
    lines: ["The Smokies’ backcountry shelters, from the Park Service itself."],
    lat: 35.71,
    lon: -83.51, // Gatlinburg, TN - the line is about the Smokies
  },
  {
    name: "Benton MacKaye Trail Association",
    lines: ["Benton MacKaye Trail trailheads, named for the man who dreamed up the A.T."],
    lat: 34.86,
    lon: -84.32, // Blue Ridge, GA
  },
  {
    name: "Foothills Trail Conservancy",
    lines: ["Foothills Trail access points along the Blue Ridge Escarpment."],
    lat: 35.0,
    lon: -82.9, // the trail itself, on the SC/NC line
  },
  {
    name: "Potomac Appalachian Trail Club",
    lines: ["The Tuscarora Trail, the A.T.’s quieter western cousin, from PATC."],
    lat: 38.9,
    lon: -77.26, // Vienna, VA
  },
  {
    name: "Pennsylvania Spatial Data Access",
    lines: ["Pennsylvania’s state forest trails and campsites. The rocks you’ll find on your own."],
    lat: 40.79,
    lon: -77.86, // State College, PA
  },
  {
    name: "Connecticut Department of Energy and Environmental Protection",
    lines: ["Connecticut’s Blue-Blazed Hiking Trails. Follow the blue, not the bars."],
    lat: 41.76,
    lon: -72.67, // Hartford, CT
  },
  {
    name: "Massachusetts Department of Conservation and Recreation",
    lines: ["The Blue Hills’ numbered junctions, so “left at the next number” makes sense."],
    lat: 42.21,
    lon: -71.08, // the Blue Hills, Milton, MA
  },
  {
    name: "The Trustees of Reservations",
    lines: ["The Trustees’ properties, from the world’s first land trust."],
    lat: 42.36,
    lon: -71.06, // Boston, MA
  },
  {
    name: "Society for the Protection of New Hampshire Forests",
    lines: ["New Hampshire woods the Forest Society keeps open to everyone."],
    lat: 43.21,
    lon: -71.54, // Concord, NH
  },
  {
    name: "New York City Department of Parks and Recreation",
    lines: ["Five boroughs of NYC Parks trails, and where the restrooms are."],
    lat: 40.77,
    lon: -73.97, // the Arsenal, Central Park
  },
  {
    name: "New York City Department of Transportation",
    lines: ["New York’s greenways, boardwalks and step streets. The city hikes too."],
    lat: 40.71,
    lon: -74.0, // Lower Manhattan
  },
];

/** "Trail data from N organizations, offline." - N counts the organizations
 *  in `roster` (orgRoster.mjs's list) with data that ships, never a
 *  hand-typed number, so it cannot go stale the way the credits strings did
 *  before #1059 and this file's own ORGS did before #1877. */
export function orgCountLine(roster) {
  const count = shipping(roster).length;
  return `Trail data from ${count} ${count === 1 ? "organization" : "organizations"}, offline.`;
}

/** The entries of `orgs` whose organization has data that ships - what the
 *  page hands its rotation. An entry naming an organization with none is
 *  dropped here, at build time, rather than kept as a claim. */
export function rotationOrgs(roster, orgs = ORGS) {
  const names = new Set(shipping(roster).map((org) => org.name));
  return orgs.filter((org) => names.has(org.name));
}

/** The full rotation: the count line first, then every line of every entry
 *  on the roster, in list order. What site/src/pages/index.astro's inline
 *  script re-derives client-side (there, to re-sort by estimated distance
 *  first) - kept here as the one place that says what the rotation holds, so
 *  a test can hold the page to it. */
export function allSlides(roster, orgs = ORGS) {
  return [orgCountLine(roster)].concat(rotationOrgs(roster, orgs).flatMap((org) => org.lines));
}
