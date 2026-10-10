// INVENTED data_quality.json files, one for each state /data/quality/ draws:
// dataQuality.test.mjs reads them, and so does the preview recipe
// (client/preview-shots/data-quality.mjs), which routes them in because no
// published release carries the file yet. NOTHING HERE WAS MEASURED, and the
// recipe's caption says so on the frame it publishes.
//
// NOBODY'S DATA. The tables that need a look are named for `preview_fixture`,
// the source key no organization holds (preview-shots/fixtures/
// releaseInjection.mjs is the precedent), so no invented anomaly is pinned on
// a real steward's table. The marts are OurHike's own models
// (pipeline/dbt/models/marts/), whose names are not anyone's data.
//
// Each export is a function returning a fresh object, so a test can break one
// to make a wrong-format file without touching the next test's copy.
//
// TWO SHAPES OF FILE. The light examples are the contract's first shape: no
// `in_needs_a_look`, no `metric` on most entries, no `mart` on a series, a
// series only behind a volume or freshness entry - what an older file looks
// like, which the page still reads whole. monthlyManyProblems and
// hourlyManyProblems are the shape the maintainer's round-3 choice asked for
// (2026-10-08): a series for every mart's row count and for every entry with
// a history, each flagged `in_needs_a_look` and naming its `mart`, every
// entry naming its metric, a failed dbt test its failing rows, hourly series
// a week long.

export const MONTHLY_BUILT_AT = "2026-10-07T06:12:00Z";
export const HOURLY_BUILT_AT = "2026-10-07T23:05:00Z";

/**
 * The moment these files are read at, for a page clock: an hour after the
 * hourly run, so a frame says "1 hour ago" whenever it is taken rather than
 * however long ago these dates now are.
 */
export const EXAMPLE_NOW = "2026-10-08T00:05:00Z";

/** Twelve monthly builds of rows in one table, steady and then 21% short. */
const MONTHLY_ROWS = [5231, 5240, 5236, 5252, 5249, 5261, 5270, 5268, 5279, 5285, 5292, 4118];

/**
 * How many builds a check needs before it can fire, at Elementary's three
 * standard deviations: 11, this build among them. What the pipeline writes
 * as `learning.needed` (pipeline/dbt/macros/data_quality.sql derives it, and
 * pipeline/dbt/dbt_project.yml has the measurement).
 */
export const NEEDED = 11;

/**
 * The band Elementary 0.26.0 stores at each point, the one it scored that
 * point against: the mean of that point and every one before it, plus or
 * minus three of their sample standard deviations
 * (get_anomaly_scores_query(): "rows between unbounded preceding and current
 * row", and DuckDB's stddev), its lower edge no lower than 0, as Elementary
 * floors a count's. None at the first point, whose one value has no spread.
 * A point counts toward its own band, so none can fall outside its band
 * before the NEEDED-th. The page draws each point against the band stored at
 * the point before it (decision 118), so an early point can sit outside the
 * band drawn there, as 7 Feb 2026's does here. Computed rather than typed, so
 * the example's band and its last entry's expected range agree.
 */
function bands(values, sigmas = 3, round = Math.round) {
  return values.map((_, i) => {
    const seen = values.slice(0, i + 1);
    if (seen.length < 2) return [null, null];
    const mean = seen.reduce((a, b) => a + b, 0) / seen.length;
    const sd = Math.sqrt(seen.reduce((a, b) => a + (b - mean) ** 2, 0) / (seen.length - 1));
    return [Math.max(0, round(mean - sigmas * sd)), round(mean + sigmas * sd)];
  });
}

const monthlyBand = bands(MONTHLY_ROWS);
const [lastMin, lastMax] = monthlyBand[monthlyBand.length - 1];

function monthlyPoints() {
  return MONTHLY_ROWS.map((value, i) => {
    const at = new Date(Date.UTC(2025, 10 + i, 7, 6, 12));
    return {
      at: at.toISOString().replace(".000Z", "Z"),
      value,
      expected_min: monthlyBand[i][0],
      expected_max: monthlyBand[i][1],
    };
  });
}

const kinds = (rows) =>
  rows.map(([kind, checks, warned = 0, failed = 0, errored = 0]) => ({
    kind,
    checks,
    passed: checks - warned - failed - errored,
    warned,
    failed,
    errored,
  }));

const totalOf = (rows) =>
  rows.reduce(
    (sum, row) => ({
      checks: sum.checks + row.checks,
      passed: sum.passed + row.passed,
      warned: sum.warned + row.warned,
      failed: sum.failed + row.failed,
      errored: sum.errored + row.errored,
    }),
    { checks: 0, passed: 0, warned: 0, failed: 0, errored: 0 },
  );

const marts = (rows) =>
  rows.map(([mart, checks, warned = 0]) => ({ mart, checks, passed: checks - warned, warned, failed: 0, errored: 0 }));

const MONTHLY_MARTS = [
  ["trail_lines", 412, 1],
  ["points_of_interest", 388],
  ["trail_network", 96],
  ["elevation", 74],
  ["places", 121],
  ["suggested_hikes", 88],
  ["challenges", 41],
  ["podcasts", 12],
  ["sources", 57],
];

/** Something to look at: three warnings, one of them with the history the chart draws. */
export function monthlyWithWarnings() {
  const byKind = kinds([
    ["freshness", 264],
    ["volume", 602, 1],
    ["schema", 590, 1],
    ["dbt_tests", 2904],
    ["anomalies", 486, 1],
  ]);
  return {
    format: "ourhike-data-quality/1",
    lane: "monthly",
    built_at: MONTHLY_BUILT_AT,
    totals: totalOf(byKind),
    kinds: byKind,
    learning: { builds: 12, needed: NEEDED },
    needs_a_look: [
      {
        kind: "volume",
        table: "preview_fixture__trails",
        column: null,
        status: "warn",
        value: MONTHLY_ROWS[MONTHLY_ROWS.length - 1],
        expected_min: lastMin,
        expected_max: lastMax,
        since: MONTHLY_BUILT_AT,
      },
      {
        kind: "anomalies",
        table: "trail_lines",
        column: "surface",
        status: "warn",
        value: 4.2,
        expected_min: 0,
        expected_max: 1.5,
        since: "2026-09-07T06:12:00Z",
        metric: "null_percent",
      },
      {
        kind: "schema",
        table: "preview_fixture__trails",
        column: "trail_class",
        status: "warn",
        value: null,
        expected_min: null,
        expected_max: null,
        since: MONTHLY_BUILT_AT,
      },
    ],
    series: [{ table: "preview_fixture__trails", metric: "row_count", points: monthlyPoints() }],
    by_mart: marts(MONTHLY_MARTS),
  };
}

/** Every check passed, with a full history behind the anomaly checks. */
export function monthlyAllGreen() {
  const byKind = kinds([
    ["freshness", 264],
    ["volume", 602],
    ["schema", 590],
    ["dbt_tests", 2904],
    ["anomalies", 486],
  ]);
  return {
    format: "ourhike-data-quality/1",
    lane: "monthly",
    built_at: MONTHLY_BUILT_AT,
    totals: totalOf(byKind),
    kinds: byKind,
    learning: { builds: 12, needed: NEEDED },
    needs_a_look: [],
    series: [],
    by_mart: marts(MONTHLY_MARTS.map(([mart, checks]) => [mart, checks])),
  };
}

/** The third monthly build: everything passes, because the anomaly checks cannot fire yet. */
export function monthlyLearning() {
  return { ...monthlyAllGreen(), learning: { builds: 3, needed: NEEDED } };
}

const HOURLY_MARTS = [
  ["closures", 143],
  ["warnings", 131],
];

/** One late source in the hourly run. */
export function hourlyWithWarning() {
  const byKind = kinds([
    ["freshness", 32, 1],
    ["volume", 40],
    ["schema", 40],
    ["dbt_tests", 300],
    ["anomalies", 6],
  ]);
  return {
    format: "ourhike-data-quality/1",
    lane: "hourly",
    built_at: HOURLY_BUILT_AT,
    totals: totalOf(byKind),
    kinds: byKind,
    learning: { builds: 168, needed: NEEDED },
    needs_a_look: [
      {
        kind: "freshness",
        table: "preview_fixture__alerts",
        column: null,
        status: "warn",
        value: 93_600,
        expected_min: 600,
        expected_max: 43_200,
        since: "2026-10-06T21:05:00Z",
      },
    ],
    series: [],
    by_mart: marts(HOURLY_MARTS),
  };
}

/** The hourly run with every check passing. */
export function hourlyAllGreen() {
  const byKind = kinds([
    ["freshness", 32],
    ["volume", 40],
    ["schema", 40],
    ["dbt_tests", 300],
    ["anomalies", 6],
  ]);
  return {
    ...hourlyWithWarning(),
    totals: totalOf(byKind),
    kinds: byKind,
    needs_a_look: [],
  };
}

// ---------------------------------------------------------------- many problems

const HOUR = 3600;
const DAY = 24 * HOUR;
const MONTH = 30.4 * DAY;

/** A small seeded generator, so every run draws the same invented file. */
function seeded(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 2 ** 32;
  };
}

/**
 * `n` points ending at `end`, `step` seconds apart, swaying gently around
 * `level` by up to `jitter` of it, the last one `last`, banded as `bands`
 * bands them. A sway rather than random noise, so no point but the last falls
 * outside its own stored band and each chart has the one finding its entry
 * names; an early point can still sit outside the narrower band the page
 * draws from the points before it. `places` rounds each value, for a rate
 * rather than a count.
 */
function history({ level, last, n, end, step, seed, jitter = 0.006, places = 0 }) {
  const phase = seeded(seed)() * 2 * Math.PI;
  const round = (v) => Math.round(v * 10 ** places) / 10 ** places;
  // At least two of its smallest step either way, or a 45-row table's sway
  // rounds away and Elementary's range reads "45 to 45".
  const sway = Math.max(level * jitter, 2 / 10 ** places);
  const values = Array.from({ length: n - 1 }, (_, i) => round(level + sway * Math.sin(i * 1.7 + phase)));
  values.push(last);
  const band = bands(values, 3, round);
  const endMs = Date.parse(end);
  return values.map((value, i) => ({
    at: new Date(endMs - (n - 1 - i) * step * 1000).toISOString().replace(".000Z", "Z"),
    value,
    expected_min: band[i][0],
    expected_max: band[i][1],
  }));
}

function entry(kind, table, status, extra = {}) {
  return { kind, table, column: null, metric: null, status, value: null, expected_min: null, expected_max: null, since: null, ...extra };
}

/**
 * The mart a table is, as the file's `mart` names it, or null for a table that
 * is no mart's. These examples name a mart's table as its folder, where the
 * pipeline's file names it by version (`trail_lines_v1`); the page joins By
 * mart on `mart` either way.
 */
function martOf(table) {
  return [...MANY_MONTHLY_MARTS, ...MANY_HOURLY_MARTS].some(([mart]) => mart === table) ? table : null;
}

/** An entry with the history behind it: the entry's figures are its history's last point. */
function withHistory(kind, table, status, { column = null, metric, points, since }) {
  const last = points[points.length - 1];
  return {
    entry: entry(kind, table, status, {
      column,
      metric,
      value: last.value,
      expected_min: last.expected_min,
      expected_max: last.expected_max,
      since,
    }),
    series: { table, column, metric, mart: martOf(table), in_needs_a_look: true, points },
  };
}

/** by_mart from the entries on marts, so the table and the list agree. */
function byMart(rows, items) {
  return rows.map(([mart, checks]) => {
    const own = items.filter((item) => item.table === mart);
    const count = (status) => own.filter((item) => item.status === status).length;
    const [warned, failed, errored] = [count("warn"), count("fail"), count("error")];
    return { mart, checks, passed: checks - warned - failed - errored, warned, failed, errored };
  });
}

/** Every mart's row count that no entry has already brought, flagged as not needing a look. */
function martRowCounts(rows, series, { end, step, n, seed }) {
  return rows
    .filter(([mart]) => !series.some((s) => s.table === mart && s.metric === "row_count" && s.column === null))
    .map(([mart, , level], i) => ({
      table: mart,
      column: null,
      metric: "row_count",
      mart,
      in_needs_a_look: false,
      points: history({ level, last: Math.round(level * 1.002), n, end, step, seed: seed + i }),
    }));
}

/** [mart, checks, rows] for the monthly marts: rows is the level its row count is drawn around. */
const MANY_MONTHLY_MARTS = [
  ["trail_lines", 412, 94140],
  ["points_of_interest", 388, 46510],
  ["trail_network", 96, 12030],
  ["elevation", 74, 8822],
  ["places", 121, 3104],
  ["suggested_hikes", 88, 201],
  ["challenges", 41, 160],
  ["podcasts", 12, 410],
  ["sources", 57, 590],
];

/**
 * The monthly build with a great deal wrong: 3 checks failed, 4 could not
 * run and 29 warned, across all five kinds - round 2's heavy file, which the
 * maintainer judged the page's long-list options against, in the round-3
 * shape. Invented; nothing here was measured.
 */
export function monthlyManyProblems() {
  const at = MONTHLY_BUILT_AT;
  const earlier = "2026-09-07T06:12:00Z";
  const monthly = (level, last, seed, extra = {}) => history({ level, last, n: 12, end: at, step: MONTH, seed, ...extra });
  const items = [];
  const series = [];
  const add = ({ entry: one, series: own }) => {
    items.push(one);
    series.push(own);
  };

  items.push(entry("dbt_tests", "trail_lines", "fail", { column: "id", value: 2, since: at }));
  items.push(entry("dbt_tests", "points_of_interest", "fail", { column: "mile", value: 13, since: earlier }));
  add(
    withHistory("anomalies", "trail_lines", "fail", {
      column: "trail_status",
      metric: "null_percent",
      points: monthly(0.3, 31, 90, { jitter: 0.3, places: 1 }),
      since: at,
    }),
  );
  items.push(entry("volume", "preview_fixture_30__trails", "error", { metric: "row_count", since: at }));
  items.push(entry("volume", "preview_fixture_05__parking", "error", { metric: "row_count", since: at }));
  items.push(entry("freshness", "preview_fixture_29__trails", "error", { metric: "freshness", since: at }));
  items.push(entry("anomalies", "elevation", "error", { column: "loss_ft", metric: "average", since: at }));

  [
    ["preview_fixture_07__water_sources", 828, 0],
    ["preview_fixture_03__trails", 5260, 4118],
    ["preview_fixture_12__shelters", 1246, 1904],
    ["preview_fixture_15__parking", 309, 233],
    ["preview_fixture_21__trailheads", 96, 70],
    ["preview_fixture_04__viewpoints", 45, 70],
    ["preview_fixture_09__trails", 14120, 12882],
    ["preview_fixture_18__water_sources", 534, 412],
    ["trail_lines", 94140, 88012],
    ["points_of_interest", 46510, 48977],
    ["preview_fixture_26__shelters", 60, 0],
    ["preview_fixture_11__trails", 2570, 2210],
  ].forEach(([table, level, last], i) =>
    add(
      withHistory("volume", table, "warn", {
        metric: "row_count",
        points: monthly(level, last, 100 + i),
        since: i % 4 === 3 ? earlier : at,
      }),
    ),
  );
  [
    ["preview_fixture_02__trails", 30, 41],
    ["preview_fixture_14__shelters", 30, 63],
    ["preview_fixture_08__viewpoints", 31, 52],
    ["preview_fixture_23__water_sources", 30, 47],
    ["preview_fixture_17__trailheads", 31, 90],
  ].forEach(([table, level, last], i) =>
    add(
      withHistory("freshness", table, "warn", {
        metric: "freshness",
        points: monthly(level * DAY, last * DAY, 200 + i, { jitter: 0.04 }),
        since: at,
      }),
    ),
  );
  for (const [table, column] of [
    ["preview_fixture_03__trails", "trail_class"],
    ["preview_fixture_12__shelters", "capacity"],
    ["preview_fixture_19__parking", "fee"],
    ["preview_fixture_06__trails", "blaze_colour"],
    ["preview_fixture_22__water_sources", "treated"],
    ["preview_fixture_13__viewpoints", "elevation_ft"],
  ]) {
    items.push(entry("schema", table, "warn", { column, since: at }));
  }
  [
    ["trail_lines", "surface", "null_percent", 0.6, 4.2, 1],
    ["elevation", "gain_ft", "max", 2750, 9812, 0],
    ["places", "name", "null_count", 3, 41, 0],
    ["points_of_interest", "water_distance_mi", "null_percent", 4, 12.5, 1],
    ["suggested_hikes", "duration_min", "average", 200, 412, 0],
    ["trail_network", "miles", "average", 2.6, 1.1, 2],
  ].forEach(([table, column, metric, level, last, places], i) =>
    add(
      withHistory("anomalies", table, "warn", {
        column,
        metric,
        points: monthly(level, last, 300 + i, { jitter: 0.05, places }),
        since: at,
      }),
    ),
  );

  series.push(...martRowCounts(MANY_MONTHLY_MARTS, series, { end: at, step: MONTH, n: 12, seed: 400 }));
  const byKind = kinds([
    ["freshness", 264, 5, 0, 1],
    ["volume", 602, 12, 0, 2],
    ["schema", 590, 6],
    ["dbt_tests", 2904, 0, 2],
    ["anomalies", 486, 6, 1, 1],
  ]);
  return {
    format: "ourhike-data-quality/1",
    lane: "monthly",
    built_at: at,
    totals: totalOf(byKind),
    kinds: byKind,
    learning: { builds: 12, needed: NEEDED },
    needs_a_look: items,
    series,
    by_mart: byMart(MANY_MONTHLY_MARTS, items),
  };
}

const MANY_HOURLY_MARTS = [
  ["closures", 143, 1210],
  ["warnings", 131, 940],
];

/**
 * The hourly run beside it: 1 failed and 6 warned, its series a week of
 * hourly runs - the newest 168, the most the file carries per series.
 */
export function hourlyManyProblems() {
  const at = HOURLY_BUILT_AT;
  const week = (level, last, seed, extra = {}) => history({ level, last, n: 168, end: at, step: HOUR, seed, ...extra });
  const items = [entry("dbt_tests", "closures", "fail", { column: "closed_until", value: 1, since: at })];
  const series = [];
  const add = ({ entry: one, series: own }) => {
    items.push(one);
    series.push(own);
  };
  [
    ["preview_fixture_19__closures", 6 * HOUR, 26 * HOUR, "2026-10-06T21:05:00Z"],
    ["preview_fixture_07__alerts", 1.5 * HOUR, 9 * HOUR, at],
    ["preview_fixture_24__notices", 9 * HOUR, 50 * HOUR, at],
  ].forEach(([table, level, last, since], i) =>
    add(withHistory("freshness", table, "warn", { metric: "freshness", points: week(level, last, 500 + i, { jitter: 0.25 }), since })),
  );
  [
    ["preview_fixture_19__closures", 17, 0],
    ["warnings", 955, 1410],
  ].forEach(([table, level, last], i) =>
    add(withHistory("volume", table, "warn", { metric: "row_count", points: week(level, last, 600 + i, { jitter: 0.02 }), since: at })),
  );
  add(
    withHistory("anomalies", "closures", "warn", {
      column: "reopens_on",
      metric: "null_percent",
      points: week(1.5, 22, 700, { jitter: 0.4, places: 1 }),
      since: at,
    }),
  );
  series.push(...martRowCounts(MANY_HOURLY_MARTS, series, { end: at, step: HOUR, n: 168, seed: 800 }));
  const byKind = kinds([
    ["freshness", 32, 3],
    ["volume", 40, 2],
    ["schema", 40],
    ["dbt_tests", 300, 0, 1],
    ["anomalies", 6, 1],
  ]);
  return {
    format: "ourhike-data-quality/1",
    lane: "hourly",
    built_at: at,
    totals: totalOf(byKind),
    kinds: byKind,
    learning: { builds: 168, needed: NEEDED },
    needs_a_look: items,
    series,
    by_mart: byMart(MANY_HOURLY_MARTS, items),
  };
}
