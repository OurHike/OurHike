// What ourhike.org/data/quality/ shows, worked out from the two files it reads
// (pipeline/ELT.md, "Data quality (decision 102)", step 4 of its order of
// work). Pure: no fetch, no DOM, no clock it was not handed. So every state
// the page can be in - nothing published, one lane only, learning, all green,
// something to look at, a fetch that failed, a file of the wrong format - is
// a vitest case (dataQuality.test.mjs) rather than something only a browser
// would show. src/scripts/dataQuality.js does the fetching and
// dataQualityHtml.mjs the markup.
//
// THE PAGE INVENTS NOTHING. Every count, table, column and mart it prints is
// read out of `data_quality.json`, the file the data-quality pass of
// pipeline/build_marts.py writes after Elementary's checks. The sentences
// around those values are composed here from numbers and names, never copied
// from a test's own message - the file carries no free text to copy (decision
// 10: public, counts only, no coordinates). What is written here rather than
// read is only what a kind of check IS (KINDS' `about`), which comes from
// ELT.md's "The checks, and where each goes", not from any build.
//
// AN HONEST UNKNOWN OUTRANKS A CONFIDENT ANSWER (CLAUDE.md). A file this page
// cannot read in full is shown as unreadable, never half-drawn; a metric whose
// unit the file does not give is printed as a bare number; and a pass from a
// check that is still learning is said to be one.

/** The one format this page reads (the file's `format`). */
export const FORMAT = "ourhike-data-quality/1";

/** The two lanes, in the order the page draws them. */
export const LANES = ["monthly", "hourly"];

/**
 * WHERE EACH LANE'S FILE IS, relative to the data base the deploy points the
 * page at (`data-base`, substituted for `__DATA_BASE_URL__` by
 * .github/scripts/configure_quality_page.py). These two strings are the ones
 * to change if publish.py settles on other keys.
 *
 * The monthly file is in the release folder the client's DATA_RELEASE pins
 * (`{release}`, substituted for `__DATA_RELEASE__` at the same step), beside
 * the release's other files, so the page built at a tag shows the checks of
 * the data that tag ships. The hourly file is at the root beside the other
 * `conditions/` files, which are rewritten in place every hour rather than
 * versioned (client/src/lib/dataRelease.ts, ROOT_SCOPED_PREFIXES).
 */
export const LANE_KEYS = {
  monthly: "releases/{release}/data_quality.json",
  hourly: "conditions/data_quality.json",
};

/**
 * How long one fetch may take before the page says the data host did not
 * answer. @unvalidated: picked, not measured. 20 s is long enough that a slow
 * phone connection is not called a failure and short enough that a captive
 * portal, which accepts the connection and never answers, does not leave the
 * page saying "Reading" for ever. What would settle it is the slowest fetch of
 * a file this size from a real phone that still completed.
 */
export const FETCH_TIMEOUT_MS = 20_000;

/** A release id, as client/src/lib/dataRelease.ts's RELEASE_ID spells one. */
export const RELEASE_ID = /^\d{4}-\d{2}-\d{2}(-\d+)?$/;

/**
 * The five kinds of check, in the order the page shows them, from the file's
 * `kind` (ELT.md, "The checks, and where each goes"). `passed` captions the
 * "N of M" figure, `problem` names a check of this kind that did not pass,
 * and `about` says what the kind covers when nothing of it needs a look.
 */
export const KINDS = [
  {
    id: "freshness",
    label: "Freshness",
    passed: "checks on time",
    problem: "late",
    about: "How long each source goes between loads, against the gap it usually keeps.",
  },
  {
    id: "volume",
    label: "Volume",
    passed: "checks at the usual size",
    problem: "unusual",
    about: "Rows per build in every raw table and every mart.",
  },
  {
    id: "schema",
    label: "Schema",
    passed: "checks with the columns expected",
    problem: "changed",
    about: "Columns added, dropped or retyped upstream, and the types each phone file declares.",
  },
  {
    id: "dbt_tests",
    label: "dbt tests",
    passed: "tests pass",
    problem: "not passing",
    about: "Keys, nulls, relationships and the marts' contracts.",
  },
  {
    id: "anomalies",
    label: "Anomalies",
    passed: "checks in the usual range",
    problem: "out of range",
    about: "Null rates, minimums and maximums on the safety columns, and counts per club.",
  },
];
const KIND = new Map(KINDS.map((kind) => [kind.id, kind]));

/**
 * The kinds whose checks compare a build with the builds before it, and so
 * wait for the file's `learning.needed` builds before they can fire: each is
 * an Elementary `*_anomalies` test (ELT.md's table). Schema changes compare
 * with the one build before (0.26.0's test_schema_changes.sql calls
 * `get_columns_changes_from_last_run_query`, read 2026-10-08), and dbt tests
 * with nothing, so neither learns.
 */
export const LEARNING_KINDS = new Set(["freshness", "volume", "anomalies"]);

/**
 * A check's status as the page words it. `rank` orders "Needs a look", worst
 * first: a failed check before one that could not run (which is a gap, not a
 * finding) before a warning. A status the page does not know is shown in the
 * file's own word, after these.
 */
export const STATUSES = {
  fail: { label: "Failed", tone: "bad", rank: 0 },
  error: { label: "Could not run", tone: "bad", rank: 1 },
  warn: { label: "Warned", tone: "warn", rank: 2 },
};
const OTHER_STATUS_RANK = 3;

/**
 * How a metric's value is worded, by Elementary's own metric names. Its
 * freshness metrics are in seconds: 0.26.0 computes both with
 * `timediff("second", ...)` (macros/edr/data_monitoring/monitors_query/
 * table_monitoring_query.sql), and its `*_percent` metrics run 0 to 100, as
 * `value / total * 100.0` (macros/utils/percent_query.sql), both read
 * 2026-10-08. If the data-quality pass converts either before writing the
 * file, this is the table to change. `floor` is the least a value can be, so a
 * band whose lower edge Elementary put below it (a mean minus deviations can
 * go negative) is printed from the floor rather than as "-3 rows".
 */
const METRICS = {
  row_count: { label: "Rows", kind: "count", unit: ["row", "rows"], floor: 0 },
  freshness: { label: "Time between updates", kind: "duration", phrase: "between updates", floor: 0 },
  event_freshness: { label: "Time from an event to its load", kind: "duration", phrase: "from event to load", floor: 0 },
  null_count: { label: "Nulls", kind: "count", floor: 0 },
  null_percent: { label: "Null rate", kind: "percent", floor: 0 },
  zero_count: { label: "Zeros", kind: "count", floor: 0 },
  zero_percent: { label: "Zero rate", kind: "percent", floor: 0 },
  missing_count: { label: "Missing values", kind: "count", floor: 0 },
  missing_percent: { label: "Missing rate", kind: "percent", floor: 0 },
  min: { label: "Minimum", kind: "number" },
  max: { label: "Maximum", kind: "number" },
  average: { label: "Average", kind: "number" },
  min_length: { label: "Shortest length", kind: "count", floor: 0 },
  max_length: { label: "Longest length", kind: "count", floor: 0 },
  average_length: { label: "Average length", kind: "number", floor: 0 },
};

/**
 * The metric a check of each kind measures when its entry does not name one.
 * A file written before entries carried `metric` (the d102 contract's first
 * shape) still says this much through `kind`: volume is Elementary's row
 * count, and freshness its freshness. The other kinds measure many metrics,
 * so without a name their values are printed as bare numbers. An entry that
 * does carry a `metric` is worded by that instead, and one whose `metric` is
 * null - a dbt test, a schema change - measures nothing a history could hold.
 */
const DEFAULT_METRIC = { volume: "row_count", freshness: "freshness" };

/** The metric a mart's own row is charted by: its row count, from the volume checks. */
const MART_METRIC = "row_count";

const COUNT_KEYS = ["checks", "passed", "warned", "failed", "errored"];
const MAX_NAME = 256;
const ISO_INSTANT = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$/;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// ---------------------------------------------------------------- formatting

const pad = (n) => String(n).padStart(2, "0");
const plural = (n, one, many) => (n === 1 ? one : many);
const group = (digits) => digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",");

/** A whole number with thousands separators: 3412 is "3,412". */
export function formatCount(n) {
  const whole = Math.round(n);
  return `${whole < 0 ? "-" : ""}${group(String(Math.abs(whole)))}`;
}

/** Any number: whole ones as counts, others to a precision that fits their size. */
export function formatNumber(x) {
  if (Number.isInteger(x)) return formatCount(x);
  const abs = Math.abs(x);
  const places = abs >= 100 ? 0 : abs >= 10 ? 1 : abs >= 1 ? 2 : 3;
  let fixed = abs.toFixed(places);
  if (fixed.includes(".")) fixed = fixed.replace(/0+$/, "").replace(/\.$/, "");
  const [whole, fraction] = fixed.split(".");
  const sign = x < 0 && fixed !== "0" ? "-" : "";
  return `${sign}${group(whole)}${fraction ? `.${fraction}` : ""}`;
}

const DURATION_UNITS = [
  ["second", 1],
  ["minute", 60],
  ["hour", 3600],
  ["day", 86400],
];
const DURATION_ABBREVIATIONS = { second: "s", minute: "min", hour: "h", day: "d" };

/** Seconds under 90, minutes under an hour, hours under two days, then days. */
function durationUnit(seconds) {
  const s = Math.abs(seconds);
  if (s < 90) return DURATION_UNITS[0];
  if (s < 3600) return DURATION_UNITS[1];
  if (s < 48 * 3600) return DURATION_UNITS[2];
  return DURATION_UNITS[3];
}

function inUnit(seconds, [, size]) {
  const amount = seconds / size;
  return Math.abs(amount) >= 10 || Number.isInteger(amount) ? Math.round(amount) : Math.round(amount * 10) / 10;
}

/** Seconds as a duration a person reads: 93600 is "26 hours". */
export function formatDuration(seconds) {
  const unit = durationUnit(seconds);
  const amount = inUnit(seconds, unit);
  return `${formatNumber(amount)} ${plural(amount, unit[0], `${unit[0]}s`)}`;
}

/**
 * Two durations in the larger one's unit, "1 to 12 hours" - or each in its
 * own, "10 minutes to 12 hours", when the smaller is under one of the larger's
 * units and would otherwise read as "0.2".
 */
export function formatDurationRange(min, max) {
  const unit = durationUnit(Math.max(Math.abs(min), Math.abs(max)));
  if (min !== 0 && Math.abs(min) < unit[1]) return `${formatDuration(min)} to ${formatDuration(max)}`;
  return `${formatNumber(inUnit(min, unit))} to ${formatNumber(inUnit(max, unit))} ${unit[0]}s`;
}

/** An instant in UTC, written out the same in every browser: "7 Oct 2026, 06:12 UTC". */
export function formatWhen(date) {
  return `${formatDay(date)}, ${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())} UTC`;
}

/** The UTC day of an instant: "7 Oct 2026". */
export function formatDay(date) {
  return `${date.getUTCDate()} ${MONTHS[date.getUTCMonth()]} ${date.getUTCFullYear()}`;
}

/**
 * A short axis label: the month and year for a monthly build, the UTC time
 * for an hourly run - with its day when the history spans more than one, as
 * an hourly series can now hold a week (its newest 168 runs), where "06:00"
 * alone would name seven different points.
 */
export function formatTickLabel(date, lane, { withDay = false } = {}) {
  if (lane === "monthly") return `${MONTHS[date.getUTCMonth()]} ${date.getUTCFullYear()}`;
  const time = `${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}`;
  return withDay ? `${date.getUTCDate()} ${MONTHS[date.getUTCMonth()]} ${time}` : time;
}

/**
 * How long ago `date` was by the visitor's clock, or null when that clock is
 * more than five minutes behind the build's: an age worked out from a clock
 * that disagrees with the build would be a guess.
 */
export function formatAge(date, now) {
  const ms = now.getTime() - date.getTime();
  if (ms < -5 * 60_000) return null;
  const minutes = Math.floor(Math.max(0, ms) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} ${plural(minutes, "minute", "minutes")} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `${hours} ${plural(hours, "hour", "hours")} ago`;
  const days = Math.floor(hours / 24);
  return `${days} ${plural(days, "day", "days")} ago`;
}

/** How one metric's values are worded, whether or not the page knows the metric. */
export function metricFormat(metric) {
  const spec = (metric && METRICS[metric]) || null;
  const floor = (v) => (spec && spec.floor !== undefined ? Math.max(spec.floor, v) : v);
  const bare = (v) => {
    if (spec?.kind === "duration") return formatDuration(v);
    if (spec?.kind === "percent") return `${formatNumber(v)}%`;
    return formatNumber(v);
  };
  return {
    metric: metric ?? null,
    known: spec !== null,
    label: spec?.label ?? (metric ? metric : "Value"),
    /** The least a value can be (null when the page does not know the metric). */
    floor: spec?.floor ?? null,
    /** Whether values are seconds, so an axis snaps to minutes, hours and days. */
    duration: spec?.kind === "duration",
    /** The value on its own, unit included where the metric has one: "4,118 rows". */
    value(v) {
      if (spec?.unit) return `${formatCount(v)} ${plural(Math.round(v), ...spec.unit)}`;
      if (spec?.kind === "duration") return `${formatDuration(v)} ${spec.phrase}`;
      if (spec) return `${spec.label}: ${bare(v)}`;
      return `Measured ${bare(v)}`;
    },
    /** An expected range: "5,231 to 5,292", "1 to 12 hours", "0% to 1.5%". */
    range(min, max) {
      const [lo, hi] = [floor(min), floor(max)];
      if (spec?.kind === "duration") return formatDurationRange(lo, hi);
      return `${bare(lo)} to ${bare(hi)}`;
    },
    /** Axis ticks, compact and in one unit: [0, 3600, 7200] is "0 h", "1 h", "2 h". */
    ticks(values) {
      if (spec?.kind !== "duration") return values.map(bare);
      const unit = durationUnit(Math.max(...values.map(Math.abs), 1));
      return values.map((v) => `${formatNumber(inUnit(v, unit))} ${DURATION_ABBREVIATIONS[unit[0]]}`);
    },
    /** A value in a table cell or the chart's readout. */
    cell(v) {
      return spec?.unit ? formatCount(v) : bare(v);
    },
  };
}

// ---------------------------------------------------------------- reading a file

class FormatError extends Error {}
const fail = (message) => {
  throw new FormatError(message);
};
const isObject = (v) => v !== null && typeof v === "object" && !Array.isArray(v);

function list(v, where) {
  if (!Array.isArray(v)) fail(`${where} is not a list`);
  return v;
}

function counts(v, where) {
  if (!isObject(v)) fail(`${where} is not an object of counts`);
  const out = {};
  for (const key of COUNT_KEYS) {
    if (!Number.isInteger(v[key]) || v[key] < 0) fail(`${where}.${key} is not a count`);
    out[key] = v[key];
  }
  return out;
}

function name(v, where, { optional = false } = {}) {
  if (optional && (v === null || v === undefined)) return null;
  if (typeof v !== "string" || v.length === 0 || v.length > MAX_NAME) fail(`${where} is not a name`);
  return v;
}

function measure(v, where) {
  if (v === null || v === undefined) return null;
  if (typeof v !== "number" || !Number.isFinite(v)) fail(`${where} is not a number`);
  return v;
}

function instant(v, where, { optional = false } = {}) {
  if (optional && (v === null || v === undefined)) return null;
  if (typeof v !== "string" || !ISO_INSTANT.test(v)) fail(`${where} is not an ISO 8601 instant`);
  // Fractional seconds cut to milliseconds before parsing: Python writes
  // microseconds, and Date.parse is only specified for three digits.
  const ms = Date.parse(v.replace(/(\.\d{3})\d+/, "$1"));
  if (Number.isNaN(ms)) fail(`${where} is not a date`);
  return new Date(ms);
}

function kind(v, where) {
  if (!KIND.has(v)) fail(`${where} is not one of the five kinds`);
  return v;
}

function parse(value, lane) {
  if (!isObject(value)) fail("the file is not a JSON object");
  if (value.format !== FORMAT) fail(`format is not ${FORMAT}`);
  if (value.lane !== lane) fail(`lane is not ${lane}`);
  const builtAt = instant(value.built_at, "built_at");
  const totals = counts(value.totals, "totals");

  const kinds = {};
  list(value.kinds, "kinds").forEach((entry, i) => {
    const id = kind(entry?.kind, `kinds[${i}].kind`);
    if (kinds[id]) fail(`kinds lists ${id} twice`);
    kinds[id] = counts(entry, `kinds[${i}]`);
  });

  if (!isObject(value.learning)) fail("learning is not an object");
  const { builds, needed } = value.learning;
  if (!Number.isInteger(builds) || builds < 0) fail("learning.builds is not a count");
  if (!Number.isInteger(needed) || needed < 1) fail("learning.needed is not a positive count");

  const items = list(value.needs_a_look, "needs_a_look").map((entry, i) => {
    const where = `needs_a_look[${i}]`;
    if (!isObject(entry)) fail(`${where} is not an object`);
    return {
      lane,
      kind: kind(entry.kind, `${where}.kind`),
      table: name(entry.table, `${where}.table`),
      column: name(entry.column, `${where}.column`, { optional: true }),
      status: name(entry.status, `${where}.status`),
      value: measure(entry.value, `${where}.value`),
      min: measure(entry.expected_min, `${where}.expected_min`),
      max: measure(entry.expected_max, `${where}.expected_max`),
      since: instant(entry.since, `${where}.since`, { optional: true }),
      metric: name(entry.metric, `${where}.metric`, { optional: true }),
      builtAt,
    };
  });

  const series = list(value.series, "series").map((entry, i) => {
    const where = `series[${i}]`;
    if (!isObject(entry)) fail(`${where} is not an object`);
    const points = list(entry.points, `${where}.points`).map((point, j) => {
      if (!isObject(point)) fail(`${where}.points[${j}] is not an object`);
      return {
        at: instant(point.at, `${where}.points[${j}].at`),
        value: measure(point.value, `${where}.points[${j}].value`),
        min: measure(point.expected_min, `${where}.points[${j}].expected_min`),
        max: measure(point.expected_max, `${where}.points[${j}].expected_max`),
      };
    });
    points.sort((a, b) => a.at - b.at);
    // Absent in a file written before the menu's two groups existed, and then
    // worked out from the entries instead (needsALook, below).
    const flag = entry.in_needs_a_look;
    if (flag !== undefined && flag !== null && typeof flag !== "boolean") {
      fail(`${where}.in_needs_a_look is not true or false`);
    }
    return {
      lane,
      table: name(entry.table, `${where}.table`),
      column: name(entry.column, `${where}.column`, { optional: true }),
      metric: name(entry.metric, `${where}.metric`),
      // The mart a versioned table is: `trail_lines_v1` is `trail_lines`, the
      // name by_mart uses. Absent for a table that is no mart's.
      mart: name(entry.mart, `${where}.mart`, { optional: true }),
      inNeedsALook: typeof flag === "boolean" ? flag : null,
      points,
    };
  });

  const marts = list(value.by_mart, "by_mart").map((entry, i) => ({
    lane,
    mart: name(entry?.mart, `by_mart[${i}].mart`),
    ...counts(entry, `by_mart[${i}]`),
  }));

  return { lane, builtAt, totals, kinds, learning: { builds, needed }, items, series, marts };
}

/**
 * The file one lane published, read in full or not at all: `{ok: true, file}`
 * or `{ok: false, why}`. `why` is for the console; the page says only that the
 * file is not in the format it reads, because a file this page cannot read is
 * not one whose half it should trust.
 */
export function readQualityFile(value, lane) {
  try {
    return { ok: true, file: parse(value, lane) };
  } catch (error) {
    if (error instanceof FormatError) return { ok: false, why: error.message };
    throw error;
  }
}

// ---------------------------------------------------------------- where to read

/**
 * What the deploy told this page, from the two placeholders it substitutes.
 * A base still reading `__...` (or empty) was never substituted, which is a
 * deployment that set no DATA_BASE_URL - the status page's own test.
 */
export function configFrom({ base, release }) {
  const trimmed = typeof base === "string" ? base.trim().replace(/\/+$/, "") : "";
  const configured = trimmed !== "" && !trimmed.startsWith("__");
  return {
    configured,
    base: configured ? trimmed : null,
    release: typeof release === "string" && RELEASE_ID.test(release) ? release : null,
  };
}

/** The URL of one lane's file, or null when this page was not told enough to find it. */
export function laneUrl(config, lane) {
  if (!config.configured) return null;
  if (lane === "monthly" && config.release === null) return null;
  return `${config.base}/${LANE_KEYS[lane].replace("{release}", config.release ?? "")}`;
}

/**
 * One lane's state from what its fetch came back with. `fetched` is
 * `{state: "read", json}`, `{state: "missing"}` (a 404), or
 * `{state: "failed", status?, timedOut?}`.
 */
export function settleLane(fetched, lane) {
  if (fetched.state !== "read") return fetched;
  const read = readQualityFile(fetched.json, lane);
  return read.ok ? { state: "ok", file: read.file } : { state: "invalid", why: read.why };
}

// ---------------------------------------------------------------- the page

const LANE_TITLE = { monthly: "Monthly build", hourly: "Hourly conditions" };
const LANE_LABEL = { monthly: "Monthly", hourly: "Hourly" };
const LANE_RUNS = { monthly: "monthly builds", hourly: "hourly runs" };
const LANE_NOUN = { monthly: "the monthly build", hourly: "the hourly run" };

const sumCounts = (entries) =>
  Object.fromEntries(COUNT_KEYS.map((key) => [key, entries.reduce((total, entry) => total + (entry?.[key] ?? 0), 0)]));

const statusOf = (status) =>
  STATUSES[status] ?? { label: status.charAt(0).toUpperCase() + status.slice(1), tone: "warn", rank: OTHER_STATUS_RANK };

/** The pills for a set of counts: passed, warnings and failed, and errored when any. */
function countPills(c) {
  const pills = [
    { tone: "ok", text: `${formatCount(c.passed)} passed` },
    { tone: c.warned > 0 ? "warn" : "ok", text: `${formatCount(c.warned)} ${plural(c.warned, "warning", "warnings")}` },
    { tone: c.failed > 0 ? "bad" : "ok", text: `${formatCount(c.failed)} failed` },
  ];
  if (c.errored > 0) pills.push({ tone: "bad", text: `${formatCount(c.errored)} could not run` });
  return pills;
}

/** One pill or two for a row whose counts are a result: "All pass", or what did not. */
function resultPills(c) {
  if (c.checks === 0) return [{ tone: "neutral", text: "None ran" }];
  const pills = [];
  if (c.failed > 0) pills.push({ tone: "bad", text: `${formatCount(c.failed)} failed` });
  if (c.warned > 0) pills.push({ tone: "warn", text: `${formatCount(c.warned)} ${plural(c.warned, "warning", "warnings")}` });
  if (c.errored > 0) pills.push({ tone: "bad", text: `${formatCount(c.errored)} could not run` });
  return pills.length ? pills : [{ tone: "ok", text: "All pass" }];
}

function card(lane, state, config, now) {
  const base = { lane, title: LANE_TITLE[lane], state: state.state, meta: "", detail: null, pills: [], learning: null };
  switch (state.state) {
    case "loading":
      return { ...base, meta: "Reading…" };
    case "unconfigured":
      return {
        ...base,
        meta: "Not configured",
        detail: config.configured
          ? "This page was published without a release to read, so it cannot find the monthly build's file."
          : null,
      };
    case "missing":
      return {
        ...base,
        meta: "Not published yet",
        detail:
          lane === "monthly"
            ? `Release ${config.release} has no data-quality file. A release carries one only when the build that made it ran the checks.`
            : "The hourly run has not published a data-quality file yet.",
      };
    case "failed":
      return {
        ...base,
        meta: "Could not be read",
        detail: state.timedOut
          ? `The data host did not answer within ${FETCH_TIMEOUT_MS / 1000} seconds.`
          : state.status
            ? `The data host answered ${state.status}.`
            : "The request did not complete: a network problem, or the data host not letting this page read it.",
      };
    case "invalid":
      return {
        ...base,
        meta: "Could not be read",
        detail: `The file is not in the format this page reads (${FORMAT}).`,
      };
    case "ok": {
      const { file } = state;
      const age = formatAge(file.builtAt, now);
      const when = `${formatWhen(file.builtAt)}${age ? `, ${age}` : ""}`;
      const { builds, needed } = file.learning;
      return {
        ...base,
        meta:
          lane === "monthly"
            ? `Made release ${config.release} · built ${when}`
            : `Trail conditions, rebuilt every hour · last run ${when}`,
        pills: countPills(file.totals),
        learning:
          builds < needed
            ? {
                text: `Learning, ${builds} of ${needed} builds`,
                detail: `Its anomaly checks compare each build with the ones before it, and wait for ${needed}. Until then they pass without being able to fire.`,
              }
            : null,
      };
    }
    default:
      throw new Error(`no card for a lane in state ${state.state}`);
  }
}

function notice(config, lanes, read) {
  if (!config.configured) {
    return {
      title: "This page is not configured",
      body: "It was published without a data source, so there is nothing for it to read. That is a problem with how the page was deployed, not a failed check.",
    };
  }
  if (read.length > 0 || LANES.some((lane) => lanes[lane].state === "loading")) return null;
  const states = LANES.map((lane) => lanes[lane].state);
  if (states.every((state) => state === "missing" || state === "unconfigured")) {
    return {
      title: "Nothing is published yet",
      body: "The checks run on every build, and each build publishes its counts beside its data. Neither file this page reads is there yet, so it has nothing to show, which is not the same as a check failing.",
    };
  }
  return {
    title: "The checks could not be read",
    body: "Nothing here is filled in from an earlier visit or a guess, so the page shows nothing rather than part of an answer. Reloading it asks again.",
  };
}

const WHY_NOT_READ = {
  loading: "is still being read",
  missing: "is not published yet",
  unconfigured: "cannot be found from how this page was published",
  failed: "could not be read",
  invalid: "could not be read",
};

/** Which builds a section's figures come from, in a sentence. */
function scopeLine(lanes, read) {
  if (read.length === 2) return "Counted across both builds above.";
  const [only] = read;
  const other = LANES.find((lane) => lane !== only.lane);
  return `Counted from ${LANE_NOUN[only.lane]} alone: ${LANE_NOUN[other]}'s file ${WHY_NOT_READ[lanes[other].state]}.`;
}

/** Text with code in it, as segments the renderer escapes: strings, and `{code}` for a name. */
const code = (text) => ({ code: text });

function itemSentence(item) {
  if (item.status === "error") return "The check could not run, so this went unchecked at this build.";
  const metric = item.metric ?? DEFAULT_METRIC[item.kind] ?? null;
  if (item.value !== null) {
    const fmt = metricFormat(metric);
    const what = `${fmt.value(item.value)} at this build`;
    if (item.min !== null && item.max !== null) {
      const range = fmt.range(item.min, item.max);
      if (item.value < item.min) return `${what}, below the ${range} Elementary expected.`;
      if (item.value > item.max) return `${what}, above the ${range} Elementary expected.`;
      return `${what}. Elementary expected ${range}.`;
    }
    return `${what}.`;
  }
  if (item.kind === "schema") return "Its columns no longer match what Elementary expected.";
  if (item.kind === "dbt_tests") return item.status === "fail" ? "A dbt test on it failed." : "A dbt test on it warned.";
  return item.status === "fail" ? "Elementary's check on it failed." : "Elementary's check on it warned.";
}

function shortSentence(item) {
  if (item.status === "error") return "could not run.";
  const metric = item.metric ?? DEFAULT_METRIC[item.kind] ?? null;
  if (item.value !== null) {
    const fmt = metricFormat(metric);
    const where =
      item.min !== null && item.max !== null
        ? item.value < item.min
          ? ", below its expected range"
          : item.value > item.max
            ? ", above its expected range"
            : ""
        : "";
    return `${fmt.value(item.value)}${where}.`;
  }
  if (item.kind === "schema") return "its columns changed.";
  if (item.kind === "dbt_tests") return item.status === "fail" ? "a dbt test failed." : "a dbt test warned.";
  return `${statusOf(item.status).label.toLowerCase()}.`;
}

/**
 * One entry as the list draws it. `id` is the row's element id, which the
 * chart's "Back to the row" link returns to; `chart` is the key of the series
 * holding this entry's own history, or null when the file holds none.
 */
function itemView(item, index, series) {
  const status = statusOf(item.status);
  const sameBuild = item.since !== null && item.since.getTime() === item.builtAt.getTime();
  const own = seriesOf(item, series);
  return {
    id: `dq-row-${index}`,
    tone: status.tone,
    status: status.label,
    rank: status.rank,
    kindId: item.kind,
    kind: KIND.get(item.kind).label,
    table: item.table,
    column: item.column,
    lane: LANE_LABEL[item.lane],
    sentence: itemSentence(item),
    since: item.since === null ? null : sameBuild ? "Since this build" : `Since ${formatWhen(item.since)}`,
    chart: own ? seriesKey(own) : null,
    chartName: own ? buttonName(own) : null,
  };
}

/** The read files' entries, worst first, the monthly build's before the hourly run's at the same rank. */
function mergedItems(read) {
  const all = read.flatMap((file) => file.items);
  return all
    .map((item, at) => ({ item, at, rank: statusOf(item.status).rank }))
    .sort((a, b) => a.rank - b.rank || a.at - b.at)
    .map(({ item }) => item);
}

/**
 * "May only mean", not "means": a kind that learns can also hold checks that
 * do not (dbt's own source freshness sits beside Elementary's under
 * Freshness), and those passes are real ones.
 */
function learningNote(read) {
  const parts = read
    .filter((file) => file.learning.builds < file.learning.needed)
    .map((file) => `${file.learning.builds} of ${file.learning.needed} ${LANE_RUNS[file.lane]}`);
  if (parts.length === 0) return null;
  return `Learning, ${parts.join(" and ")}: until then a pass may only mean an anomaly check cannot fire yet.`;
}

function tile(kind, read, items, learning) {
  const c = sumCounts(read.map((file) => file.kinds[kind.id]));
  let pills;
  if (c.checks === 0) pills = [{ tone: "neutral", text: "None ran" }];
  else {
    pills = [];
    const problems = c.warned + c.failed;
    if (problems > 0) pills.push({ tone: c.failed > 0 ? "bad" : "warn", text: `${formatCount(problems)} ${kind.problem}` });
    if (c.errored > 0) pills.push({ tone: "bad", text: `${formatCount(c.errored)} could not run` });
    if (pills.length === 0) pills.push({ tone: "ok", text: "All pass" });
  }
  const own = items.filter((item) => item.kind === kind.id);
  const note = own.length
    ? [code(own[0].table), `: ${shortSentence(own[0])}`, own.length > 1 ? ` And ${own.length - 1} more below.` : ""]
    : [kind.about];
  return {
    id: kind.id,
    label: kind.label,
    pills,
    figure: c.checks === 0 ? { passed: "0", checks: null } : { passed: formatCount(c.passed), checks: formatCount(c.checks) },
    caption: c.checks === 0 ? "checks of this kind ran" : kind.passed,
    note,
    learning: LEARNING_KINDS.has(kind.id) && c.checks > 0 ? learning : null,
  };
}

// ---------------------------------------------------------------- the series

/**
 * One series' identity on the page - lane, table, column and metric - as the
 * value the Show menu's options and the Chart buttons carry. JSON rather than
 * the four joined by a separator, because a name from a file may hold any
 * character a separator could be.
 */
export function seriesKey(series) {
  return JSON.stringify([series.lane, series.table, series.column ?? null, series.metric]);
}

/** Every series the read files hold, once each: a second copy of a key is dropped. */
function uniqueSeries(read) {
  const seen = new Set();
  return read
    .flatMap((file) => file.series)
    .filter((series) => {
      const key = seriesKey(series);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

/**
 * The series that is `item`'s own history, or null. Same lane, table, column
 * and metric: a column's null rate is not its neighbour's, and a series that
 * names no column is a table's own (its row count, its freshness). An entry
 * that names no metric - a dbt test, a schema change - has no history and
 * matches nothing. It once matched any series on its table, so a failed dbt
 * test on `trail_lines` drew trail_lines' row count as if that were what
 * failed (round 2's heavy file, 2026-10-08).
 */
function seriesOf(item, series) {
  const metric = item.metric ?? DEFAULT_METRIC[item.kind];
  if (!metric) return null;
  return (
    series.find(
      (s) =>
        s.lane === item.lane && s.table === item.table && (s.column ?? null) === (item.column ?? null) && s.metric === metric,
    ) ?? null
  );
}

/**
 * A mart's own row count, or null when the file holds none for it. Joined
 * by the series' `mart` where it names one, and else by its table: C1's
 * test-warehouse file (2026-10-08) writes the versioned table
 * (`trail_lines_v1`) with `mart: "trail_lines"`, while by_mart names the mart
 * alone, so a join on the table found no mart and By mart drew no Chart
 * button.
 */
function martSeries(mart, series) {
  return (
    series.find(
      (s) =>
        s.lane === mart.lane &&
        (s.mart ?? s.table) === mart.mart &&
        (s.column ?? null) === null &&
        s.metric === MART_METRIC,
    ) ?? null
  );
}

/**
 * What a series is, in words: "Rows in trail_lines · Monthly", or "Null rate
 * of surface in trail_lines · Monthly" for a column's - the Show menu's
 * option text.
 */
export function seriesName(series, sep = " · ") {
  const fmt = metricFormat(series.metric);
  const what = fmt.known ? fmt.label : series.metric;
  return `${what}${series.column ? ` of ${series.column}` : ""} in ${series.table}${sep}${LANE_LABEL[series.lane]}`;
}

/**
 * The name a screen reader hears for a Chart button: its one visible word
 * first, then the series - "Chart rows in trail_lines, Monthly". A comma
 * where the menu has " · ", which a reader may speak as "dot".
 */
function buttonName(series) {
  const name = seriesName(series, ", ");
  return `Chart ${name.charAt(0).toLowerCase()}${name.slice(1)}`;
}

/**
 * Whether a series belongs under "Needs a look" in the Show menu rather than
 * "Every mart": the file's `in_needs_a_look` says so, and a file written
 * before that field existed is answered from its entries - a series some
 * entry draws its history from needs a look.
 */
function needsALook(series, items) {
  if (series.inNeedsALook !== null) return series.inNeedsALook;
  return items.some((item) => seriesOf(item, [series]) !== null);
}

/**
 * The Show menu's two groups. "Needs a look" lists its series in the order
 * the list above it does, worst first; "Every mart" in By mart's order. A
 * series is listed once, in the group its flag puts it in, so a mart whose
 * row count needs a look is under "Needs a look" and not again under "Every
 * mart" - the shape the maintainer chose from (round 2's frames, 2026-10-08).
 * A group with nothing in it is left out.
 */
function menuOf(series, items, marts) {
  const look = [];
  const other = [];
  const placed = new Set();
  const place = (list, s) => {
    const key = seriesKey(s);
    if (placed.has(key)) return;
    placed.add(key);
    list.push(s);
  };
  for (const item of items) {
    const own = seriesOf(item, series);
    if (own && needsALook(own, items)) place(look, own);
  }
  for (const mart of marts) {
    const own = martSeries(mart, series);
    if (own && !needsALook(own, items)) place(other, own);
  }
  for (const s of series) place(needsALook(s, items) ? look : other, s);
  return {
    look,
    other,
    groups: [
      { label: "Needs a look", options: look },
      { label: "Every mart", options: other },
    ]
      .filter((group) => group.options.length > 0)
      .map((group) => ({
        label: group.label,
        options: group.options.map((s) => ({ key: seriesKey(s), label: seriesName(s) })),
      })),
  };
}

/**
 * The series the chart opens on: the history behind the worst entry that has
 * one; when no entry has one, the first mart's row count the menu lists; and
 * failing both, the first series the files hold.
 */
function pickSeries(series, items, menu) {
  for (const item of items) {
    const own = seriesOf(item, series);
    if (own) return own;
  }
  return menu.other[0] ?? series[0] ?? null;
}

function outsideOf(point) {
  if (point.value === null || point.min === null || point.max === null) return null;
  if (point.value < point.min) return "below";
  if (point.value > point.max) return "above";
  return null;
}

function chartView(series, read) {
  if (series === null) return null;
  const fmt = metricFormat(series.metric);
  const file = read.find((candidate) => candidate.lane === series.lane);
  const points = series.points.map((point) => ({ ...point, outside: outsideOf(point) }));
  const drawn = points.filter((point) => point.value !== null);
  const outside = points.filter((point) => point.outside !== null);
  const each = series.lane === "monthly" ? "monthly build" : "hourly run";
  const what = fmt.known ? fmt.label : "Values";
  const title = series.column
    ? [`${what} of `, code(series.column), " in ", code(series.table), `, one point per ${each}`]
    : [`${what} in `, code(series.table), `, one point per ${each}`];

  let summary;
  if (drawn.length === 0) summary = "No build in this history recorded a value.";
  else {
    const first = drawn[0];
    const last = drawn[drawn.length - 1];
    summary =
      drawn.length === 1
        ? `One ${each} so far: ${fmt.cell(first.value)} on ${formatDay(first.at)}.`
        : `${drawn.length} ${LANE_RUNS[series.lane]}, from ${fmt.cell(first.value)} on ${formatDay(first.at)} to ${fmt.cell(last.value)} on ${formatDay(last.at)}.`;
    summary +=
      outside.length === 0
        ? " None falls outside the range Elementary expected."
        : ` ${outside.length} of them ${outside.length === 1 ? "falls" : "fall"} outside the range Elementary expected.`;
  }
  const unbanded = points.some((point) => point.min === null || point.max === null);
  const caption = [
    "The shaded band is the range Elementary expected at each point, worked out from the ones before it. A point outside it is drawn as a triangle and named.",
    unbanded && file
      ? ` Points with no band came before Elementary had the ${file.learning.needed} earlier ${LANE_RUNS[series.lane]} it waits for.`
      : "",
  ].join("");

  return {
    key: seriesKey(series),
    lane: series.lane,
    table: series.table,
    column: series.column ?? null,
    metric: series.metric,
    format: fmt,
    title,
    summary,
    caption,
    points,
    // A monthly build is named by its day; an hourly run needs its time too.
    // The table's header says UTC, so the cells need not.
    rows: points.map((point) => ({
      when: series.lane === "monthly" ? formatDay(point.at) : formatWhen(point.at).replace(/ UTC$/, ""),
      whenFull: formatWhen(point.at),
      value: point.value === null ? "No value" : fmt.cell(point.value),
      expected:
        point.min === null || point.max === null
          ? "No range yet"
          : `${fmt.range(point.min, point.max)}${point.outside ? `, ${point.outside} it` : ""}`,
      where: whereInRange(point),
    })),
  };
}

function whereInRange(point) {
  if (point.outside === "below") return "Below the range";
  if (point.outside === "above") return "Above the range";
  if (point.value === null || point.min === null || point.max === null) return "Not compared";
  return "Inside the range";
}

/**
 * The most warnings a kind can hold and still open by itself. A kind with
 * more stays folded behind its one line.
 *
 * THE MAINTAINER'S FIGURE, chosen by poll on 2026-10-08 against round 3's
 * fork-2 frames: a light build's four one-warning kinds, drawn all folded and
 * drawn open. It is a decision, not a measurement - nobody has measured how
 * many rows a reader takes in before a fold starts to help.
 */
export const OPEN_FOLD_MAX = 3;

/**
 * "Needs a look" as the maintainer chose it by poll on 2026-10-08 (option D
 * of round 2's frames): every entry that failed, could not run, or reports a
 * status this page does not know is listed in full; only warnings are folded,
 * one line per kind that opens, and a kind with OPEN_FOLD_MAX or fewer opens
 * by itself. A failure is never behind a fold however many there are -
 * folding is what a long list of warnings gets, and a failure hidden by one
 * is the thing a reader came to find.
 */
function lookView(items) {
  const failing = items.filter((item) => item.rank < STATUSES.warn.rank);
  const other = items.filter((item) => item.rank === OTHER_STATUS_RANK);
  const warnings = items.filter((item) => item.rank === STATUSES.warn.rank);
  const folded = KINDS.map((kind) => {
    const own = warnings.filter((item) => item.kindId === kind.id);
    return {
      kind: kind.id,
      label: kind.label,
      summary: `${formatCount(own.length)} ${plural(own.length, "warning", "warnings")}`,
      open: own.length <= OPEN_FOLD_MAX,
      items: own,
    };
  }).filter((group) => group.items.length > 0);
  return {
    failing: { title: `Failed or could not run · ${formatCount(failing.length)}`, items: failing },
    // A status this page does not know is not a warning it can vouch for, so
    // it is listed with the failures rather than folded with the warnings.
    other: { title: `Other results · ${formatCount(other.length)}`, items: other },
    warnings: { title: `Warnings · ${formatCount(warnings.length)}, by kind`, count: warnings.length, folded },
  };
}

function sectionsView(lanes, read) {
  const merged = mergedItems(read);
  const learning = learningNote(read);
  const totals = sumCounts(read.map((file) => file.totals));
  const problems = totals.warned + totals.failed + totals.errored;
  const where = read.length === 2 ? "either build above" : LANE_NOUN[read[0].lane];

  let quiet = null;
  if (merged.length === 0) {
    quiet =
      problems === 0
        ? `Nothing needs a look: no check in ${where} warned, failed or could not run.${learning ? " The anomaly checks are still learning, so a quiet result says less than it will once they have their history." : ""}`
        : `${formatCount(problems)} ${plural(problems, "check needs", "checks need")} a look by the counts above, and the ${plural(read.length, "file lists", "files list")} none of them.`;
  }

  const series = uniqueSeries(read);
  const fileMarts = read.flatMap((file) => file.marts);
  const menu = menuOf(series, merged, fileMarts);
  const charts = new Map(series.map((s) => [seriesKey(s), chartView(s, read)]));
  const first = pickSeries(series, merged, menu);
  const items = merged.map((item, i) => itemView(item, i, series));
  const marts = fileMarts.map((mart, i) => {
    const own = martSeries(mart, series);
    return {
      id: `dq-mart-${i}`,
      mart: mart.mart,
      lane: LANE_LABEL[mart.lane],
      checks: formatCount(mart.checks),
      checksPhrase: `${formatCount(mart.checks)} ${plural(mart.checks, "check", "checks")}`,
      pills: resultPills(mart),
      chart: own ? seriesKey(own) : null,
      chartName: own ? buttonName(own) : null,
    };
  });

  // The row whose Chart button starts pressed: the entry pickSeries took the
  // first chart from, or else the mart it fell back to. Null when the first
  // series has no button at all.
  const firstKey = first ? seriesKey(first) : null;
  const opening =
    firstKey === null
      ? null
      : ((items.find((item) => item.chart === firstKey) ?? marts.find((mart) => mart.chart === firstKey))?.id ?? null);

  return {
    scope: scopeLine(lanes, read),
    tiles: KINDS.map((kind) => tile(kind, read, merged, learning)),
    items,
    look: lookView(items),
    quiet,
    chart: firstKey === null ? null : charts.get(firstKey),
    opening,
    charts,
    menu: menu.groups,
    // Every Chart button the page draws, by the row it sits on: what the
    // chart's "Charted from" line names, and where "Back to the row" goes.
    buttons: [
      ...items.filter((item) => item.chart).map((item) => ({ row: item.id, key: item.chart, from: "Needs a look", table: item.table, column: item.column })),
      ...marts.filter((mart) => mart.chart).map((mart) => ({ row: mart.id, key: mart.chart, from: "By mart", table: mart.mart, column: null })),
    ],
    marts,
  };
}

// ---------------------------------------------------------------- choosing a series

/**
 * What the chart shows: a series' key, and the row whose Chart button stands
 * for it (null when the Show menu chose it). As the page opens that row is
 * the one the first chart came from, so its button starts pressed - the
 * maintainer's answer to round 3's fork 1, by poll on 2026-10-08. A warning's
 * row keeps its fold closed when the fold would be (OPEN_FOLD_MAX): its
 * button is pressed inside it, and "Back to the row" opens the fold.
 */
export function initialChart(sections) {
  return { key: sections.chart?.key ?? null, origin: sections.opening ?? null };
}

/** A choice in the Show menu: that series, from no row. */
export function chooseFromMenu(key) {
  return { key, origin: null };
}

/** A Chart button on row `row`: that row's series, remembered so the chart can say where it came from. */
export function chooseFromRow(sections, row) {
  const button = sections.buttons.find((candidate) => candidate.row === row);
  return button ? { key: button.key, origin: row } : null;
}

/**
 * Everything the chart's controls show for `state`, worked out here so the
 * browser only applies it. THE MENU AND THE BUTTONS STAY IN STEP, by the two
 * rules the maintainer's round-3 choice set (2026-10-08): pressing a Chart
 * button sets the menu to that button's series, and a choice in the menu
 * clears any pressed button that names another series. One row's button is
 * pressed at a time - the first chart's row as the page opens
 * (initialChart), then the row last pressed - so a pressed button always
 * means "this row is what the chart shows", and the chart's "Charted from"
 * line is there exactly when one is. A menu choice presses none. `pressed`
 * lists rows, not buttons: a mart's row holds two buttons, one for each
 * width, and both read as pressed.
 */
export function chartControls(sections, state) {
  const origin =
    state.origin === null ? null : (sections.buttons.find((button) => button.row === state.origin && button.key === state.key) ?? null);
  return {
    chart: sections.charts.get(state.key) ?? null,
    selected: state.key,
    pressed: origin ? [origin.row] : [],
    charted: origin ? { from: origin.from, table: origin.table, column: origin.column, row: origin.row } : null,
  };
}

function colophonLine(read) {
  if (read.length === 0) return null;
  const parts = read.map((file) => `${LANE_NOUN[file.lane]} of ${formatWhen(file.builtAt)}`);
  return `Made from ${parts.join(" and ")}.`;
}

/**
 * Everything the page draws, from what each lane's fetch came to. `monthly`
 * and `hourly` are lane states: `loading`, `unconfigured`, `missing`,
 * `failed`, `invalid`, or `ok` with the file `readQualityFile` read.
 */
export function buildPage({ config, monthly, hourly, now = new Date() }) {
  const lanes = { monthly, hourly };
  const read = LANES.filter((lane) => lanes[lane].state === "ok").map((lane) => lanes[lane].file);
  return {
    loading: LANES.some((lane) => lanes[lane].state === "loading"),
    cards: LANES.map((lane) => card(lane, lanes[lane], config, now)),
    notice: notice(config, lanes, read),
    sections: read.length > 0 ? sectionsView(lanes, read) : null,
    colophon: colophonLine(read),
  };
}
