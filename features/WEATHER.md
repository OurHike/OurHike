# Weather — a forecast for the trail a hiker is on, and its honest age when they are out of signal

Tracked as **[#1056](https://github.com/OurHike/OurHike/issues/1056) — v2: weather on Today, on
a waypoint, and along a planned route — 90 forecast points cannot map to 8,469 waypoints, so
forecast the coordinate rather than match it**. That issue's measurements are the reason this
doc exists and are not repeated here; read it for why matching a forecast feed to waypoints
tops out at 0.8% of them.

**Status, 2026-09-24: designed, with a spike run; not built.** This doc owns **forecasts** —
where they come from, how precise they are, how often they change, how they reach a phone,
and what a hiker sees when the phone has not heard anything for a while. It also owns how a
relayed **NWS warning** is *displayed* as it ages, because a forecast card and a warning
line age on the same screen and one rule has to govern both.
[HIKER_SAFETY.md](HIKER_SAFETY.md) §3 keeps what it already owned: *relay, don't originate*,
and the open question of whether a warning ever becomes a push notification.

## What the maintainer set, 2026-09-24

Taken in session by poll, against the first mock of the three surfaces:

- **Doc and spike before any build**, starting with research into sources.
- **Not only the A.T.** — "We're no longer just doing the AT. Find a different source if
  needed", with Pirate Weather named as one to look at.
- **Delivery: a scheduled publish to R2**, the same road closures take — over a phone calling
  a weather service itself, and over a backend proxy.
- **"More precise than the grid squares… along each trail."**
- **"It probably should update every hour if on the user's phone"**, and the doc has to think
  about what happens when somebody **has not had a data connection in 12+ hours**.

Every section below answers one of those.

## What the maintainer decided, 2026-09-24, second poll

Taken against the offline mock (one card at three ages) and §3's accuracy table:

- **The offline rules in §5, as drawn.**
- **Temperature for the first two days from HRRR corrected for elevation, NBM after that** —
  chosen over NBM uncorrected throughout, which §3 had recommended. §3 says what that choice
  means field by field.
- **GitHub's scheduler as it is, ~4 hours** — over an outside hourly trigger and over moving
  the job off GitHub. §4 says what age a hiker will actually see.
- **#1056 stays open as the program issue** until the build is done; the build order at the
  foot of this doc is its checklist rather than a set of new issues.

---

## 1. What "along each trail" means, measured

Measured 2026-09-24 against production release `2026-09-23`
(`nearby_trails.geojson` + `trails.geojson`), with the script kept in the pull request that
added this doc:

| | |
|---|---|
| Trail the app draws | **142,299 mi** across 13 sources (US Forest Service 123,612 mi; NH GRANIT 5,641; NYS DEC 4,269; NJ statewide 3,563; NYS Parks 2,745; the rest under 1,100 each) plus the A.T. centerline, 2,452 mi |
| 1° × 1° cells that trail touches | **469** — the grid [OFFLINE_COVERAGE.md](OFFLINE_COVERAGE.md) already downloads in |
| A point every 1 km along every trail | **172,777** after merging points within the same 1 km bin (343,350 before) |
| Distinct ~2.5 km forecast grid squares under that trail | **~74,330** (an equal-area approximation of NOAA's 2.5 km Lambert grid — close, not exact) |

**The consequence decides the source before any licence does.** One forecast per grid square
per hour is ~74,330 lookups an hour, **~1.8 million a day**; one per kilometre of trail is
~4.1 million. No per-point weather API in [§2](#2-sources)'s table offers that on a free
tier, and the paid ones that could either forbid republishing the result or cost thousands a
month. So the job cannot ask a service about each point. **It has to download the model's
own grid and read the points off it** — which NOAA publishes, free and without a quota.

## 2. Sources

Surveyed 2026-09-24 by reading each source's current terms and pricing pages; where a
figure was measured rather than read, the row says so. The legal question is not "may a
phone show this" but **"may we fetch it hourly and republish it to the public from our own
bucket"**, because that is the shape the maintainer chose.

| Source | Republish from our bucket? | Volume | Resolution | Cadence |
|---|---|---|---|---|
| **NOAA NBM on AWS** (`noaa-nbm-pds` as tiled GeoTIFF, `noaa-nbm-grib2-pds` as GRIB2) | **Yes** — NOAA open data, "can be used as desired" | **No quota** — whole grids | 2.5 km, CONUS (Alaska, Hawaii and Puerto Rico are separate NBM grids) | hourly cycles |
| **NOAA NDFD on AWS** (`noaa-ndfd-pds`) | **Yes** — same terms | No quota | 2.5 km | "as often as once every half hour" |
| NWS `api.weather.gov` | **Yes** — public domain | unpublished rate limit; one grid square per call; an API key is announced but "not ready to flip that switch yet" (NWS, 2025-11-27) | 2.5 km | as forecasters edit; `Cache-Control: max-age=3600` (measured) |
| **Pirate Weather** | **Unclear** — its terms never mention redistribution, and say it "should not be used for life or property critical applications" | Free plan 10,000 calls/**month** "for personal use" ≈ 14 points an hour; the largest listed plan, $350/month, is 5M/month ≈ 164k/day | docs say both 3 km (HRRR) and "the closest 13 km model square" | NBM/HRRR hourly |
| Open-Meteo (hosted) | **Yes**, with attribution — but the free tier is non-commercial only | 10,000 calls/day, and every coordinate counts as a call (measured on its own calculator) | NBM 2.5 km, HRRR 3 km | hourly |
| Open-Meteo (self-hosted on its CC BY 4.0 data) | **Yes**, commercial allowed | no quota; ≥ 8 GB RAM, ≥ 100 GB NVMe | same | same |
| MET Norway Locationforecast | **Yes** — NLOD 2.0 / CC BY 4.0 | ≤ 20 requests/s per application | ~9 km ECMWF outside the Nordics, **updated 4× a day**; no precipitation probability | 6-hourly |
| Apple WeatherKit | **No** — no "secondary or derived database" | 500k/month | — | — |
| Tomorrow.io | **No** — may not "store… the unaltered Datafeed" | 500/day free | — | — |
| Visual Crossing | **No** below Enterprise — "Storable for shared external use ✘" | 1,000/day free | — | — |
| WeatherAPI.com | **Unclear** — forecast caching capped at "maximum 24 hours", which a phone offline for a day already breaks | 100k/month free | — | — |
| OpenWeatherMap | Yes, under ODbL share-alike | 1,000/day free, then $0.0015/call (≈ $2,200/month at 50k/day) | — | every 10 min |

Pages read, 2026-09-24:
[pirate-weather.apiable.io plans](https://pirate-weather.apiable.io/products/weatherdata/plans) and
[terms](https://pirate-weather.apiable.io/terms);
[docs.pirateweather.net data sources](https://docs.pirateweather.net/en/latest/DataSources/);
[open-meteo.com terms](https://open-meteo.com/en/terms) and [licence](https://open-meteo.com/en/licence);
[api.met.no terms](https://api.met.no/doc/TermsOfService);
[weather.gov API docs](https://www.weather.gov/documentation/services-web-api) and
[disclaimer](https://www.weather.gov/disclaimer);
[registry.opendata.aws/noaa-nbm](https://registry.opendata.aws/noaa-nbm/);
Apple's Developer Program License Agreement, Attachment 8;
[tomorrow.io terms](https://www.tomorrow.io/legal/terms-of-service/);
[visualcrossing.com pricing](https://www.visualcrossing.com/weather-data-pricing/);
[weatherapi.com terms](https://www.weatherapi.com/terms.aspx);
[openweathermap.org pricing](https://openweathermap.org/price).

### Pirate Weather, since it was asked about by name

It is a good project and the wrong fit here, for three separate reasons, any one of which
would be enough:

1. **Volume.** 1.8 million calls a day against 10,000 a month; even its $350 Enterprise plan
   (5 million a month) covers about 9% of the need. It takes one coordinate per call.
2. **Terms.** "Personal use" on the free plan, "should not be used for life or property
   critical applications" on every plan, and nothing either way about republishing.
3. **It is a re-publisher of the same NOAA data.** Its own data-sources page lists NBM first
   for hourly data in the US, then HRRR. Downloading NBM from NOAA gets the forecast Pirate
   Weather would have served, without the quota or the question.

One more thing its docs turned up that is worth knowing even though we are not using it:
north of **41.7° N** Pirate Weather prefers Canadian models (HRDPS, then REPS) over NBM — a
line that runs just south of the Catskills, with Harriman on one side and Slide Mountain
on the other. A source that switches models mid-map is a source
whose forecast can jump at a line nobody drew on purpose.

### The source: NOAA's NBM, with HRRR for the first two days' temperature

**NOAA's National Blend of Models**, fetched from its AWS open-data bucket and sampled by our
own job, is the forecast. **HRRR**, from the same place, supplies temperature for the first 48
hours (the maintainer's call; §3). Reasons for NBM, each resting on something in this doc:

- **It is the only kind of source that fits the volume** (§1): whole grids, no quota, and
  NOAA's open-data terms — "can be used as desired" (§9).
- **It scored best of the full-range models** in the spike (§3): 2.7 °F mean error on
  tomorrow's high, uncorrected, against 4.0 °F for GFS and 2.8 °F for ECMWF *after*
  correction.
- **It is what NWS's own forecasts start from**, and what Pirate Weather serves first.
- **It covers everywhere the map does** — the CONUS grid for about 436 of the 469 cells,
  and NBM's separate Alaska and Puerto Rico grids for the rest (32 cells in Alaska, one in
  Puerto Rico, counted from line endpoints on the same release).

**How the job reads it, measured 2026-09-23/24:**

- **From the Cloud-Optimized GeoTIFF bucket, `noaa-nbm-pds`, not the GRIB2 one.** A COG is
  tiled (256 × 256 cells, 70 tiles per CONUS field), so the job downloads only the tiles
  over trail. Temperature, precipitation probability, wind, gust, sky cover and thunder
  probability out to seven days came to **54 MB per cycle** for the seven tiles over the
  A.T., New York and New Jersey, against 565–680 MB for the same fields as GRIB2 byte
  ranges. The whole-CONUS COG set is 384 MB; the national network touches most of CONUS's
  tiles, so expect the job to sit nearer that figure than the 54 MB one (reasoned).
- **Every hourly cycle reaches 259–264 hours**, stepping hourly to hour 48, then 3-hourly to
  about hour 190, then 6-hourly — so the five-day card never runs out of NBM.
- **Cycles land 36 minutes to 2 hours after their nominal time**, with outliers to 2 h 37 m
  and one cycle still missing at 90 minutes. The job takes the newest complete cycle rather
  than the one the clock says should exist.
- **The COG path carries the model version** (`blendv5.0/`, since NBM v5.0 went operational
  on 2026-05-05; it was `blendv4.3/` before). The job discovers it rather than hard-coding it.
- **HRRR** (`noaa-hrrr-bdp-pds`, 3 km) runs hourly but reaches 48 hours only from the 00, 06,
  12 and 18 UTC cycles; the others stop at 18. Its temperature subset for a 48-hour cycle is
  ~409 MB as GRIB2 byte ranges. **It carries no probabilities**, which is why HRRR can only
  ever be the temperature half of the first two days.

The alternative a reviewer should weigh is **NDFD**, the forecaster-edited grid behind
`api.weather.gov`: same resolution, same terms, and a human in the loop. The spike could not
score it — Open-Meteo does not archive it — so preferring NBM over it is **reasoned, not
measured** (§3's limits say what would settle it). Two things measured on 2026-09-24 count
against it anyway: its bulk files carry **no hourly precipitation probability** (only
12-hour) and **no thunder probability** outside a text weather field, and at one hour's
comparison it sat within 0–4 °F of NBM at the seven sample points.

**Warnings come from `api.weather.gov/alerts/active`, and it is one call.** Measured
2026-09-24 00:23 UTC: 596 active alerts nationwide in one response, 2.8 MB (193 KB
compressed). Only 69 carry their own polygon; the rest name NWS forecast zones — 664
distinct zones that hour — so the zone outlines are static data that ship with a data
release, and the hourly job publishes only the list. Most of those 596 are marine; the job
keeps the ones whose zone or polygon touches one of the 469 trail cells.

## 3. How precise — and what "finer than the grid" actually buys

Every forecast is a grid underneath. NBM's squares are 2.5 km, so two trail points in the
same square get the same forecast unless something corrects one of them. **The only
correction with physics behind it is temperature against elevation** — take the grid
square's model height, the trail point's real height, and apply a lapse rate. The mock the
maintainer answered drew a forecast at Lake of the Clouds Hut, and #1056 found two forecast
points 3.3 miles apart there disagreeing by 9.2 °F. So the spike measured exactly this.

**The spike: `pipeline/spike_weather_sources.py`.** Archived "tomorrow" forecasts (Open-Meteo's
Previous Runs API, used here only as an archive) against what eight weather stations
actually recorded (Iowa Environmental Mesonet's ASOS archive), 61 days, 2026-07-24 to
2026-09-22, each forecast scored twice: the raw grid square, and corrected to a 90 m DEM's
height at the station. Error in tomorrow's daily high, °F, mean absolute (bias in brackets,
forecast minus observed):

| Station | Height | NBM raw | NBM corrected | HRRR raw | HRRR corrected | GFS raw | GFS corrected |
|---|---|---|---|---|---|---|---|
| Mount Washington summit (A.T.) | 1,910 m | **2.8** (−2.0) | 4.5 (−4.3) | 6.6 (+6.5) | **2.1** (−1.2) | 16.1 (+16.1) | 5.1 (+3.1) |
| Berlin, NH (valley) | 353 m | 2.7 | 2.5 | 3.0 | 2.6 | 3.8 | 2.5 |
| Lake Placid, NY | 531 m | 3.4 | 2.1 | 2.5 | 2.4 | 4.0 | 2.4 |
| Ashe County, NC | 969 m | 1.7 | 1.9 | 2.2 | 1.6 | 3.8 | 3.8 |
| Stampede Pass, WA (PCT) | 1,209 m | 1.8 | 3.1 | 2.7 | 2.7 | 5.7 | 4.3 |
| Wolf Creek Pass, CO (CDT) | 3,584 m | 4.8 | 5.0 | 3.0 | 2.3 | 8.2 | 5.3 |
| Red Cliff Pass, CO | 3,680 m | 2.7 | 2.0 | 5.1 | 2.2 | 4.8 | 2.9 |
| Berthoud Pass, CO (CDT) | 3,792 m† | 1.8 | 2.7 | 6.1 | 2.3 | 10.2 | 5.7 |
| **Mean of the eight** | | **2.7** | 3.0 | 3.9 | **2.3** | 7.1 | 4.0 |

† IEM's metadata; Berthoud Pass is nearer 3,450 m, so that station's corrected column is
doubtful. The full table, including daily lows and ECMWF, is what the script prints.

**What it says:**

- **Correcting NBM made it worse** — at Mount Washington from 2.8 °F to 4.5 °F, and on
  average from 2.7 to 3.0. The reasonable explanation (reasoned, not measured) is that NBM is
  already calibrated against observations on a terrain-following grid, so a second
  correction counts the mountain twice.
- **Correction rescues the coarse models, and HRRR** — GFS at Mount Washington goes from
  16.1 °F wrong to 5.1; HRRR from 6.6 to 2.1, the best day-1 score in the table. But HRRR
  forecasts only 18–48 hours ahead, so it cannot fill a five-day card on its own.
- **This doc recommended NBM uncorrected throughout; the maintainer chose HRRR corrected for
  the first two days' temperature.** The case for that choice is the best day-1 high in the
  table, 2.3 °F against NBM's 2.7. The case against, recorded so the build does not rediscover
  it: **the win is on highs only** — tomorrow's low scored 2.8 °F both ways — and it buys a
  second model, a correction step, and a seam at hour 48 where the temperature source changes.

**What that decision means, field by field:**

| | Hours 0–48 | After hour 48 |
|---|---|---|
| Temperature (hourly, high, low) | **HRRR, corrected** from its grid cell's height to the trail point's height | NBM, uncorrected |
| Precipitation and thunder probability, sky, wind, gust | NBM, uncorrected — HRRR has no probabilities | NBM, uncorrected |

**The seam is per hour, not at a day boundary.** HRRR reaches 48 hours only from its
six-hourly cycles, so on GitHub's ~4-hour clock (§4) the HRRR run in a publish can already be
~8 hours old (reasoned: six hours between 48-hour cycles plus up to ~2 hours to land) and
cover only ~40 of the next 48 hours. The job uses HRRR for each hour it covers and NBM for
every hour after, so "the first two days" is a ceiling, not a promise.

So "along each trail" becomes genuinely finer than the grid for the first two days'
temperature — every trail point gets its own correction from its own height — and stays at
NBM's 2.5 km square for everything else. Compared with what #1056 started from — 90 points, a
median 3.8 miles from the waypoint — even the uncorrected square puts every point within about
1.1 miles of its forecast's centre.

**Three things the build owes this decision**, because the spike measured something close to
it rather than it:

- **The spike scored Open-Meteo's correction, not ours.** Ours will be a lapse rate applied
  from HRRR's cell height to the height in our own DEM. Until the spike is re-run with that
  exact arithmetic, the 2.3 °F is **@unvalidated** for the thing we ship. The re-run is
  cheap: the archive and the stations are already in the script.
- **The seam at hour 48 must not draw a step.** Day 2's high from HRRR and day 3's from NBM
  are different models; a hiker comparing them is comparing two sources without being
  told. The card says which days are "adjusted for elevation" (§9 requires saying it anyway).
- **A corrected value is our number, not NOAA's**, and NOAA's terms say a modified value may
  not be presented as unaltered NOAA data (§9).

**What the spike cannot say**, and a reader should not borrow its confidence for:

- **Only temperature.** Precipitation, wind and thunderstorms have no correction to test,
  and scoring whether a shower was forecast takes more than one summer.
- **Only summer.** A fixed lapse rate is at its worst in winter inversions, when a valley is
  colder than the ridge above it — which now matters more, since HRRR's first two days are
  corrected with one. Whether the correction still helps in January is **@unvalidated**;
  re-running the script over a December–February window settles it, and that re-run is in
  the build order below.
- **Eight stations**, chosen for relief rather than at random, and 51–61 days each.
- **No NDFD** — the one plausible rival to NBM is the one it could not score.

## 4. How often

**The forecast itself changes about hourly.** NBM and HRRR each run a new cycle every hour;
nothing a hiker reads can usefully be fresher than the model behind it, so **hourly is the
right ceiling for the publish** — faster buys bytes, not information.

**Three things stand between an hourly model and an hourly phone**, and only the first is
code:

1. **The phone side already exists.** `client/src/lib/useConditions.ts` re-reads the
   published conditions every `CONDITIONS_REFRESH_MS` (one hour) while the app is open, and
   again when the app comes back to the foreground, at most once per
   `VISIBILITY_REFRESH_MIN_MS` (five minutes). Weather is one more artifact on that clock;
   it needs no new timer.
2. **GitHub's scheduler does not fire hourly.** `publish-conditions.yml` declares
   `40 * * * *` and, measured 2026-09-21, fires every **3 h 53 m** on average (30 runs over
   112.6 hours, max gap 5 h 45 m) — **#1346 — Every cron in this repository fires about five
   times a day, whatever it declares — including the conditions bake**. **The maintainer
   accepted that for weather, 2026-09-24.** What it means for a hiker in signal, reasoned
   from the two measurements: a cycle lands up to ~2 hours after its nominal time, and the
   published file then waits up to 5 h 45 m for the next run, so **the forecast a phone reads
   in signal is typically 2–4 hours old and at worst about 7½**. The age line shows the
   cycle's own time, so the hiker sees that rather than infers it. One consequence worth
   knowing: at the worst gaps that age passes §5's 6-hour mark for the hour-by-hour row, so
   the row will sometimes grey while the phone has signal. That is §5's rule working —
   the timing *is* that old — not a bug to suppress.
3. **A phone in a pocket does not refresh.** A PWA cannot run on a timer while it is closed:
   Periodic Background Sync is "not Baseline" (MDN, read 2026-09-24), and even in Chrome is
   granted only to an installed app and paced by how much it is used. So the forecast a
   hiker has when they lose signal is **the one fetched the last time the app was open with
   signal**, not the one from an hour before they lost it. Capacitor
   ([#101](https://github.com/OurHike/OurHike/issues/101)) would add OS-scheduled background
   fetch, which both mobile OSes ration; that is a later improvement, not this design's
   floor.

The third point is why §5 matters more than the cadence does: **what a hiker carries into
the backcountry is whatever the app last saw.**

## 5. After 12 hours without signal — and after three days

The maintainer was shown these rules drawn as one card at three ages (a mock, not committed
— working drawings stay out of the tree). The rules, and what each rests on:

**Temperature ages slowly, so it stays on the card.** Measured by the same spike, averaged
over the eight stations, uncorrected NBM, error in tomorrow's high: **2.7 °F** from a
forecast made one day before, **2.9** two days before, **3.1** three, **3.2** four, **3.5**
five. A day without signal costs about 0.2 °F. Hiding a forecast because it is 12 hours old
would throw away something that is still nearly as good as a fresh one.

**Warnings do not age — they go blind.** A warning issued after the phone's last contact
cannot be on the phone. So past the point the phone last heard, the warning line stops
showing the last answer as if it were current and says **"No word on weather warnings since
5:40 pm"** — and never **"No warnings"**. This is the rule `useConditions.ts` already
applies to closures ("Null means 'we have not managed to ask', not 'there are none'"),
carried to weather.

**The timing of showers and storms is where a forecast is least trustworthy, so the
hour-by-hour row is the first thing to go grey.** Reasoned, not measured — the spike scores
only temperature. The row greys once the forecast is older than a
proposed `HOURLY_TRUST_HOURS`, **@unvalidated** at 6 hours: picked as half the 12 hours the
maintainer named, with nothing behind it. What would settle it: scoring the hourly
precipitation-probability forecast against observed precipitation by lead time, from the
same archive, over a season with convective storms.

**Days roll forward by the calendar, never by position.** A forecast fetched on Wednesday
read on Friday shows Friday's forecast as Friday's, labelled with how far ahead it was made
("made 2 d before"). The card never shows "day 1" meaning Wednesday on a Friday.

**Past the last forecast day, the card says "no forecast".** It never repeats the last day
and never extrapolates. NBM's range runs well past the five days the card shows; the phone
still holds only what it last fetched.

**The age is always on screen**, in the same voice `conditionState.ts` already uses for
closures ("Conditions as of 3h ago"): *"Forecast from 7:40 am · checked 12 min ago"* in
signal, *"Forecast from yesterday 5:40 pm · no signal since"* out of it.

## 6. Two ways the job can print a plausible wrong number

Found by the NOAA survey, 2026-09-24, and both belong in the job's tests before anything
reaches a card — a number that looks right and is not is the failure
[CLAUDE.md](../CLAUDE.md)'s safety section exists for:

- **Half the NBM grid comes back mirrored if it is decoded the obvious way.** NBM (and NDFD)
  use GRIB scanning mode 80: alternate rows run in opposite directions.
  `eccodes.codes_get_values` does not un-reverse them, while the latitude and longitude arrays
  come back normalised — so values and coordinates disagree silently. Measured: Springer
  Mountain read **89.5 °F instead of 62.9 °F**, and Slide Mountain 72.4 °F instead of 46.3 °F.
  cfgrib, pygrib and Herbie handle it; the COG files do not have the problem. A test pins a
  known point against a known value.
- **The nearest grid cell can be water.** Bear Mountain's published coordinate sits by the
  Hudson, and its nearest NBM cell's terrain height is **0 m** — a river cell, 391 m below
  the summit. Corrected from there, the summit would be credited with 391 m of lapse; left
  uncorrected, it reads a river-moderated temperature. The job picks the nearest *land* cell
  and a test pins Bear Mountain.

**Where the heights come from.** The correction needs HRRR's cell height, which rides in
HRRR's own files — at Mount Washington, 1,306 m against a real 1,917 — and each trail point's
real height, from the DEM the app already ships. Picking a *land* cell on NBM's grid needs
NBM's terrain, which NBM does not publish; **URMA's surface-height field** is on the identical
2.5 km grid (verified to 10⁻⁴°), so it is fetched once and cached.

## 7. How it reaches a phone

**One file per 1° cell, per publish**, under `conditions/weather/`, carrying every 2.5 km
grid square in that cell that trail touches. The cell is
[OFFLINE_COVERAGE.md](OFFLINE_COVERAGE.md)'s grid, so "which weather does this phone hold"
has the same answer as "which map does this phone hold", and `lib/coverageCells.ts` already
knows the phone's cells.

**Which cells a phone fetches:** the cells under its planned hike and its current stretch,
plus the cell it is standing in — never all 469. A hiker who has not set a hike gets the
cell under them and its neighbours.

**What a trail point reads:** its NBM grid square, found by the same projection the job
used — and, for the hours HRRR covers, its HRRR cell's temperature and that cell's height,
from which the phone applies the lapse to the point's own height. Everything that does not
change hourly rides with the data release rather than the hourly file: which squares and
cells each trail point and waypoint falls in, and each point's height. So the hourly file
carries one row of numbers per square or cell and stays per-square in size, while the
correction is still per point.

**Sizes (reasoned, not measured):** 48 hourly steps × ~6 fields, plus 5 daily summaries,
at a byte each, is ~310 bytes per grid square; ~158 squares per trail cell on average
(74,330 ÷ 469) is ~50 KB per cell per hour before compression, and a hiker holding a
five-cell stretch downloads a few hundred KB an hour at most. The job's own R2 writes are
469 objects an hour, ~340,000 a month — a third of R2's free allowance of one million
Class A operations a month (Cloudflare's pricing page, read 2026-09-24), which the other
publishes already draw on, and $4.50 a million past it.

**What the job downloads each run** (§2's measurements): NBM's COG tiles over trail, up to
~384 MB, plus a 48-hour HRRR temperature subset, ~409 MB, plus one alerts request — about
0.8 GB a run, ~5 GB a day at the measured six runs a day. That is AWS open-data egress, which
costs this project nothing, and GitHub-hosted runner time.

**UA and production publish separately**, like every other conditions artifact
([DATA_ENVIRONMENTS.md](DATA_ENVIRONMENTS.md)). Weather does not differ between the two, but
the publishing path does, and UA is where it rehearses.

## 8. What longtrailsweather.net is still for

Recommending against it as the source is not recommending ignoring it, and #1056 says why:
it is **a validation oracle** (90 independently produced forecasts to check ours against —
if we disagree by 10 °F at Lake of the Clouds, one of us is wrong), **prior art on
presentation**, and a project with a mission close to ours
([OurHikeValues.md](../OurHikeValues.md) #3 and #6). Its own data comes from Pirate Weather,
so everything §2 says about republishing Pirate Weather applies to republishing it.

## 9. Licence and attribution

NOAA's open-data terms for NBM, HRRR and NDFD on AWS, read 2026-09-24 at
[registry.opendata.aws/noaa-nbm](https://registry.opendata.aws/noaa-nbm/): *"open to the
public and can be used as desired. … NOAA requests attribution for the use or dissemination
of unaltered NOAA data. However, it is not permissible to state or imply endorsement by or
affiliation with NOAA. If you modify NOAA data, you may not state or imply that it is
original, unaltered NOAA data."* NWS alerts are public domain by the
[weather.gov disclaimer](https://www.weather.gov/disclaimer). Nothing needs asking.

**That last sentence of NOAA's governs the card.** HRRR temperature corrected for elevation is
modified data, so days 1–2 cannot be credited plainly to NOAA: they say *"NOAA forecast,
adjusted for elevation by OurHike"*, and days 3 onward, unmodified, say *"NOAA forecast"*.
`sources.json` gets a row for each, in the shape the other open sources use.

---

## Still open

- **NBM or NDFD** for everything but the first two days' temperature. NBM is recommended on
  measurement and on fields; NDFD is the forecaster-edited alternative the spike could not
  score. Not put to the maintainer yet.

## Build order

#1056 carries these as its checklist (maintainer, 2026-09-24). Each is useful alone:

1. **The job** — fetch NBM's COG tiles, HRRR's 48-hour temperature and active alerts; sample
   the trail grid squares, correcting HRRR temperature from its cell height to each trail
   point's; publish per-cell files and the alerts list to UA. §6's two tests come with it.
   No client change.
2. **The spike re-run with our own correction** (§3) — before phase 3 puts a corrected
   number in front of a hiker.
3. **The waypoint card** — the five days at the waypoint's grid square, with the age line,
   §5's rules and §9's credit lines.
4. **Today** — start and end of the day, and the warnings line.
5. **The plan** — each day's forecast at that night's camp.
6. **The winter re-run** of the spike, before the first winter, to see whether the
   correction still helps in inversions.
