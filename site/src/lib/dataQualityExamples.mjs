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
 * The band Elementary would draw at each point: the mean of the points before
 * it, plus or minus three standard deviations, once seven came before it
 * (Elementary 0.26.0's defaults, pipeline/ELT.md "What the spike measured").
 * Computed rather than typed, so the example's band and its last entry's
 * expected range agree.
 */
function bands(values, needed = 7, sigmas = 3) {
  return values.map((_, i) => {
    const prior = values.slice(0, i);
    if (prior.length < needed) return [null, null];
    const mean = prior.reduce((a, b) => a + b, 0) / prior.length;
    const sd = Math.sqrt(prior.reduce((a, b) => a + (b - mean) ** 2, 0) / prior.length);
    return [Math.round(mean - sigmas * sd), Math.round(mean + sigmas * sd)];
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
    learning: { builds: 12, needed: 7 },
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
    learning: { builds: 12, needed: 7 },
    needs_a_look: [],
    series: [],
    by_mart: marts(MONTHLY_MARTS.map(([mart, checks]) => [mart, checks])),
  };
}

/** The third monthly build: everything passes, because the anomaly checks cannot fire yet. */
export function monthlyLearning() {
  return { ...monthlyAllGreen(), learning: { builds: 3, needed: 7 } };
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
    learning: { builds: 7, needed: 7 },
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
