// /data/quality/'s rules, from invented example files (dataQualityExamples.mjs),
// one block per state the page draws: not configured, reading, nothing
// published, a fetch that failed, a file of the wrong format, one lane only,
// learning, all green, and something to look at (pipeline/ELT.md decision 102,
// step 4). The markup is dataQualityHtml.test.mjs's; this is what the page says.

import { describe, expect, it } from "vitest";
import {
  FETCH_TIMEOUT_MS,
  FORMAT,
  buildPage,
  chartControls,
  chooseFromMenu,
  chooseFromRow,
  configFrom,
  formatAge,
  formatCount,
  formatDuration,
  formatDurationRange,
  formatNumber,
  formatWhen,
  OPEN_FOLD_MAX,
  initialChart,
  laneUrl,
  NO_RANGE,
  readQualityFile,
  seriesKey,
  settleLane,
} from "./dataQuality.mjs";
import * as examples from "./dataQualityExamples.mjs";

const NOW = new Date("2026-10-08T01:00:00Z");
const CONFIG = configFrom({ base: "https://data.example.invalid/", release: "2026-10-03-2" });
const read = (json, lane) => settleLane({ state: "read", json }, lane);
const page = (monthly, hourly, now = NOW) => buildPage({ config: CONFIG, monthly, hourly, now });
const MISSING = { state: "missing" };
const tile = (view, id) => view.sections.tiles.find((t) => t.id === id);
const texts = (pills) => pills.map((p) => p.text);

describe("where the page reads its two files", () => {
  it("reads the monthly file from the pinned release's folder and the hourly one beside the conditions files", () => {
    expect(laneUrl(CONFIG, "monthly")).toBe(
      "https://data.example.invalid/releases/2026-10-03-2/data_quality.json",
    );
    expect(laneUrl(CONFIG, "hourly")).toBe("https://data.example.invalid/conditions/data_quality.json");
  });

  it("takes a base the deploy never substituted to mean no base at all", () => {
    const config = configFrom({ base: "__DATA_BASE_URL__", release: "__DATA_RELEASE__" });
    expect(config.configured).toBe(false);
    expect(laneUrl(config, "monthly")).toBeNull();
    expect(laneUrl(config, "hourly")).toBeNull();
    expect(configFrom({ base: "  ", release: "2026-10-03-2" }).configured).toBe(false);
  });

  it("cannot find the monthly file without a release id, and still finds the hourly one", () => {
    const config = configFrom({ base: "https://data.example.invalid", release: "__DATA_RELEASE__" });
    expect(laneUrl(config, "monthly")).toBeNull();
    expect(laneUrl(config, "hourly")).toBe("https://data.example.invalid/conditions/data_quality.json");
  });
});

describe("reading a file", () => {
  it.each([
    ["monthlyWithWarnings", "monthly"],
    ["monthlyAllGreen", "monthly"],
    ["monthlyLearning", "monthly"],
    ["hourlyWithWarning", "hourly"],
    ["hourlyAllGreen", "hourly"],
    ["monthlyManyProblems", "monthly"],
    ["hourlyManyProblems", "hourly"],
  ])("reads the example %s", (example, lane) => {
    expect(readQualityFile(examples[example](), lane)).toMatchObject({ ok: true });
  });

  const broken = {
    "another format": (f) => ({ ...f, format: "ourhike-data-quality/2" }),
    "the other lane's file": (f) => ({ ...f, lane: "hourly" }),
    "a count that is not a whole number": (f) => ({ ...f, totals: { ...f.totals, passed: 1.5 } }),
    "a negative count": (f) => ({ ...f, totals: { ...f.totals, warned: -1 } }),
    "a kind this page does not know": (f) => ({ ...f, kinds: [...f.kinds, { ...f.kinds[0], kind: "vibes" }] }),
    "a kind listed twice": (f) => ({ ...f, kinds: [...f.kinds, f.kinds[0]] }),
    "a learning target of zero": (f) => ({ ...f, learning: { builds: 3, needed: 0 } }),
    "a built_at that is not an instant": (f) => ({ ...f, built_at: "last Tuesday" }),
    "an entry with no table": (f) => ({ ...f, needs_a_look: [{ ...f.needs_a_look[0], table: "" }] }),
    "an entry whose value is text": (f) => ({ ...f, needs_a_look: [{ ...f.needs_a_look[0], value: "4118" }] }),
    "a series point with no time": (f) => ({
      ...f,
      series: [{ ...f.series[0], points: [{ value: 1, expected_min: null, expected_max: null }] }],
    }),
    "a by_mart that is not a list": (f) => ({ ...f, by_mart: {} }),
    "an in_needs_a_look that is not true or false": (f) => ({
      ...f,
      series: [{ ...f.series[0], in_needs_a_look: "yes" }],
    }),
    "a series column that is not a name": (f) => ({ ...f, series: [{ ...f.series[0], column: 7 }] }),
  };

  it.each(Object.keys(broken))("refuses %s, whole", (what) => {
    const result = readQualityFile(broken[what](examples.monthlyWithWarnings()), "monthly");
    expect(result.ok).toBe(false);
    expect(result.why).toEqual(expect.any(String));
  });

  it("refuses something that is not a JSON object", () => {
    for (const value of [undefined, null, "data_quality", [], 3]) {
      expect(readQualityFile(value, "monthly").ok).toBe(false);
    }
  });

  it("reads a time with microseconds, as Python writes one", () => {
    const file = { ...examples.hourlyAllGreen(), built_at: "2026-10-07T23:05:00.123456Z" };
    expect(readQualityFile(file, "hourly").file.builtAt.toISOString()).toBe("2026-10-07T23:05:00.123Z");
  });

  it("puts a series' points in time order whatever order the file lists them in", () => {
    const file = examples.monthlyWithWarnings();
    file.series[0].points.reverse();
    const points = readQualityFile(file, "monthly").file.series[0].points;
    expect(points.map((p) => p.at.getTime())).toEqual([...points.map((p) => p.at.getTime())].sort((a, b) => a - b));
  });

  it("reads each series' in_needs_a_look and column, and a file written before either existed", () => {
    const series = readQualityFile(examples.monthlyManyProblems(), "monthly").file.series;
    expect(new Set(series.map((s) => s.inNeedsALook))).toEqual(new Set([true, false]));
    expect(series.find((s) => s.column === "trail_status")).toMatchObject({ table: "trail_lines", metric: "null_percent" });
    const older = readQualityFile(examples.monthlyWithWarnings(), "monthly").file.series;
    expect(older.map((s) => [s.inNeedsALook, s.column])).toEqual([[null, null]]);
  });

  it("turns a body that was not JSON into a file of the wrong format, and passes every other state through", () => {
    expect(settleLane({ state: "read", json: undefined }, "hourly").state).toBe("invalid");
    expect(settleLane(MISSING, "hourly")).toBe(MISSING);
  });
});

describe("the page, state by state", () => {
  it("not configured: says so, and reads nothing", () => {
    const config = configFrom({ base: "__DATA_BASE_URL__", release: "__DATA_RELEASE__" });
    const view = buildPage({ config, monthly: { state: "unconfigured" }, hourly: { state: "unconfigured" }, now: NOW });
    expect(view.cards.map((c) => c.meta)).toEqual(["Not configured", "Not configured"]);
    expect(view.notice.title).toBe("This page is not configured");
    expect(view.notice.body).toContain("not a failed check");
    expect(view.sections).toBeNull();
    expect(view.colophon).toBeNull();
  });

  it("reading: both cards say so, and nothing else is drawn yet", () => {
    const view = page({ state: "loading" }, { state: "loading" });
    expect(view.loading).toBe(true);
    expect(view.cards.map((c) => c.meta)).toEqual(["Reading…", "Reading…"]);
    expect(view.notice).toBeNull();
    expect(view.sections).toBeNull();
  });

  it("nothing published yet: names the release it looked in, and is not a failure", () => {
    const view = page(MISSING, MISSING);
    expect(view.cards[0].meta).toBe("Not published yet");
    expect(view.cards[0].detail).toContain("Release 2026-10-03-2 has no data-quality file");
    expect(view.cards[1].detail).toBe("The hourly run has not published a data-quality file yet.");
    expect(view.notice.title).toBe("Nothing is published yet");
    expect(view.notice.body).toContain("not the same as a check failing");
    expect(view.sections).toBeNull();
  });

  it("a fetch that fails: says how, and shows nothing rather than part of an answer", () => {
    const view = page({ state: "failed", status: 503 }, { state: "failed", timedOut: true });
    expect(view.cards.map((c) => c.meta)).toEqual(["Could not be read", "Could not be read"]);
    expect(view.cards[0].detail).toBe("The data host answered 503.");
    expect(view.cards[1].detail).toBe(`The data host did not answer within ${FETCH_TIMEOUT_MS / 1000} seconds.`);
    expect(page({ state: "failed" }, MISSING).cards[0].detail).toContain("The request did not complete");
    expect(view.notice.title).toBe("The checks could not be read");
    expect(view.sections).toBeNull();
  });

  it("a file of the wrong format: says which format it reads, and draws nothing of that file", () => {
    const monthly = read({ ...examples.monthlyWithWarnings(), format: "ourhike-data-quality/2" }, "monthly");
    const hourly = read(examples.hourlyWithWarning(), "hourly");
    const view = page(monthly, hourly);
    expect(view.cards[0].detail).toBe(`The file is not in the format this page reads (${FORMAT}).`);
    expect(view.sections.scope).toBe(
      "Counted from the hourly run alone: the monthly build's file could not be read.",
    );
    const hourlyChecks = examples.hourlyWithWarning().kinds.find((k) => k.kind === "dbt_tests").checks;
    expect(tile(view, "dbt_tests").figure.checks).toBe(formatCount(hourlyChecks));
    expect(view.sections.marts.every((row) => row.lane === "Hourly")).toBe(true);
  });

  it("one lane only: counts that lane's file and says why the other is missing", () => {
    const file = examples.monthlyWithWarnings();
    const view = page(read(file, "monthly"), MISSING);
    expect(view.cards[1].meta).toBe("Not published yet");
    expect(view.sections.scope).toBe(
      "Counted from the monthly build alone: the hourly run's file is not published yet.",
    );
    const volume = file.kinds.find((k) => k.kind === "volume");
    expect(tile(view, "volume").figure).toEqual({
      passed: formatCount(volume.passed),
      checks: formatCount(volume.checks),
    });
    expect(view.sections.marts.map((row) => row.mart)).toEqual(file.by_mart.map((m) => m.mart));
    expect(view.colophon).toBe("Made from the monthly build of 7 Oct 2026, 06:12 UTC.");
  });

  it("learning: says how far, on the card and on each kind that learns, and that a pass means less", () => {
    const view = page(read(examples.monthlyLearning(), "monthly"), MISSING);
    expect(examples.NEEDED).toBe(11);
    expect(view.cards[0].learning.text).toBe("Learning, 3 of 11 builds");
    expect(view.cards[0].learning.detail).toBe(
      "Its anomaly checks compare each build with the ones before it, and need 11 builds, this one included, before any can fire. Until then they pass without being able to.",
    );
    for (const id of ["freshness", "volume", "anomalies"]) {
      expect(tile(view, id).learning).toBe(
        "Learning, 3 of 11 monthly builds: until then a pass may only mean an anomaly check cannot fire yet.",
      );
    }
    expect(tile(view, "schema").learning).toBeNull();
    expect(tile(view, "dbt_tests").learning).toBeNull();
    expect(view.sections.quiet).toContain("still learning");
  });

  it("all green: nothing needs a look, every kind passes, and there is no chart", () => {
    const view = page(read(examples.monthlyAllGreen(), "monthly"), read(examples.hourlyAllGreen(), "hourly"));
    expect(view.sections.items).toEqual([]);
    expect(view.sections.quiet).toBe(
      "Nothing needs a look: no check in either build above warned, failed or could not run.",
    );
    expect(view.sections.tiles.map((t) => texts(t.pills))).toEqual(Array(5).fill(["All pass"]));
    expect(view.sections.chart).toBeNull();
    expect(view.cards[0].learning).toBeNull();
    expect(view.colophon).toBe(
      "Made from the monthly build of 7 Oct 2026, 06:12 UTC and the hourly run of 7 Oct 2026, 23:05 UTC.",
    );
  });

  describe("something to look at", () => {
    const monthly = examples.monthlyWithWarnings();
    const hourly = examples.hourlyWithWarning();
    const view = page(read(monthly, "monthly"), read(hourly, "hourly"));
    const [volume] = monthly.needs_a_look;

    it("counts each card from its own file's totals", () => {
      expect(texts(view.cards[0].pills)).toEqual([
        `${formatCount(monthly.totals.passed)} passed`,
        `${monthly.totals.warned} warnings`,
        "0 failed",
      ]);
      expect(view.cards[1].meta).toBe("Trail conditions, rebuilt every hour · last run 7 Oct 2026, 23:05 UTC, 1 hour ago");
    });

    it("names what did not pass on each kind", () => {
      expect(view.sections.tiles.map((t) => texts(t.pills))).toEqual([
        ["1 late"],
        ["1 unusual"],
        ["1 changed"],
        ["All pass"],
        ["1 out of range"],
      ]);
      expect(tile(view, "volume").note).toEqual([
        { code: volume.table },
        ": 4,118 rows, below its expected range.",
        "",
      ]);
    });

    it("words each entry from its numbers and names, the monthly build's first", () => {
      expect(view.sections.items.map((item) => [item.kind, item.table, item.column, item.lane])).toEqual([
        ["Volume", "preview_fixture__trails", null, "Monthly"],
        ["Anomalies", "trail_lines", "surface", "Monthly"],
        ["Schema", "preview_fixture__trails", "trail_class", "Monthly"],
        ["Freshness", "preview_fixture__alerts", null, "Hourly"],
      ]);
      const [rows, nulls, columns, late] = view.sections.items.map((item) => item.sentence);
      expect(rows).toBe("4,118 rows at this build, below the 5,199 to 5,322 expected from the builds before.");
      // The light files carry no history for these two entries (the contract's first shape), so neither row has a
      // range from the builds before to quote; each says so and keeps Elementary's verdict.
      expect(nulls).toBe(
        "Null rate: 4.2% at this build, with no range from the builds before to compare it with. Elementary flagged it above its own range, which counts this build.",
      );
      expect(columns).toBe("Its columns no longer match what Elementary expected.");
      expect(late).toBe(
        "26 hours between updates at this build, with no range from the builds before to compare it with. Elementary flagged it above its own range, which counts this build.",
      );
      expect(view.sections.items.map((item) => item.since)).toEqual([
        "Since this build",
        "Since 7 Sep 2026, 06:12 UTC",
        "Since this build",
        "Since 6 Oct 2026, 21:05 UTC",
      ]);
    });

    it("draws the history behind the worst entry that has one, each point against the band stored at the point before it", () => {
      const { chart } = view.sections;
      const stored = monthly.series[0].points;
      const range = (point) => `${formatCount(point.expected_min)} to ${formatCount(point.expected_max)}`;
      expect(chart.table).toBe("preview_fixture__trails");
      expect(chart.points.map((point) => [point.min, point.max])).toEqual([
        [null, null],
        ...stored.slice(0, -1).map((point) => [point.expected_min, point.expected_max]),
      ]);
      // The table shows the band the chart draws, row by row: none at the first point, which has no point before
      // it, nor at the second, whose point before is a check's first and was never scored.
      expect(chart.rows.map((row) => row.expected)).toEqual([
        NO_RANGE,
        NO_RANGE,
        ...stored.slice(1, -2).map(range),
        `${range(stored.at(-2))}, flagged below`,
      ]);
      expect(chart.rows.at(-1)).toMatchObject({ when: "7 Oct 2026", value: "4,118", where: "Flagged below the range" });
      expect(chart.summary).toBe(
        "12 monthly builds, from 5,231 on 7 Nov 2025 to 4,118 on 7 Oct 2026. Elementary flagged 1 of them in its latest checks.",
      );
    });

    it("leaves 7 Feb 2026 unflagged above the band from the three builds before it, as the caption warns", () => {
      const { chart } = view.sections;
      expect(chart.rows[3]).toEqual({
        when: "7 Feb 2026",
        whenFull: "7 Feb 2026, 06:12 UTC",
        value: "5,252",
        expected: "5,222 to 5,249",
        where: null,
      });
      expect(chart.points[3].value).toBeGreaterThan(chart.points[3].max);
      expect(chart.points[3].outside).toBeNull();
    });

    it('says the band is the range expected from the builds before each point, and a triangle is Elementary\'s verdict ("No range" without one)', () => {
      const { chart } = view.sections;
      expect(NO_RANGE).toBe("No range");
      expect(chart.caption).toBe(
        "The shaded band at each point is the range Elementary expected from the monthly builds before it: the band it worked out at the point before, which does not count the point itself. A triangle marks a point Elementary flagged. Elementary judges a point against a band that does count it, so a point can sit outside the shaded band without a triangle, and none can be flagged before its check has 11 monthly builds. A point with no band is this chart's first, or comes after one no run scored, such as a check's first.",
      );
    });

    it("flags only the point a warned or failed entry reports, by its value and range, whatever band the chart draws there", () => {
      const flags = (change) => {
        const file = examples.monthlyWithWarnings();
        change(file.needs_a_look[0]);
        return page(read(file, "monthly"), MISSING).sections.chart.points.map((point) => point.outside);
      };
      const last = [...Array(11).fill(null), "below"];
      expect(flags(() => {})).toEqual(last);
      expect(flags((entry) => (entry.status = "fail"))).toEqual(last);
      // A check that could not run judged nothing, though 4,118 sits far below the band drawn there.
      expect(flags((entry) => (entry.status = "error"))).toEqual(Array(12).fill(null));
      // An entry whose figures are no point's cannot be placed, so nothing is flagged in its name.
      expect(flags((entry) => (entry.value = 4117))).toEqual(Array(12).fill(null));
      expect(flags((entry) => (entry.expected_min = entry.expected_min - 1))).toEqual(Array(12).fill(null));
    });
  });

  it("puts what failed before what could not run before a warning, whichever lane it came from", () => {
    const monthly = examples.monthlyWithWarnings();
    const hourly = examples.hourlyWithWarning();
    hourly.needs_a_look.push(
      { kind: "dbt_tests", table: "warnings", column: "id", status: "fail", value: null, expected_min: null, expected_max: null, since: null },
      { kind: "volume", table: "closures", column: null, status: "error", value: null, expected_min: null, expected_max: null, since: null },
    );
    const items = page(read(monthly, "monthly"), read(hourly, "hourly")).sections.items;
    expect(items.map((item) => item.status).slice(0, 3)).toEqual(["Failed", "Could not run", "Warned"]);
    expect(items[0]).toMatchObject({ tone: "bad", sentence: "A dbt test on it failed.", since: null });
    expect(items[1].sentence).toBe("The check could not run, so this went unchecked at this build.");
  });

  it("charts the worst entry's own history, never another check's on the same table", () => {
    // A failed dbt test names no metric, so nothing in the file is its
    // history; the table's row count belongs to a different check, and the
    // volume entry below it is the one with a history.
    const file = examples.monthlyWithWarnings();
    file.needs_a_look.unshift({
      kind: "dbt_tests",
      table: "trail_lines",
      column: "id",
      status: "fail",
      value: null,
      expected_min: null,
      expected_max: null,
      since: null,
    });
    file.series.unshift({ ...file.series[0], table: "trail_lines" });
    const { chart } = page(read(file, "monthly"), MISSING).sections;
    expect(chart.table).toBe("preview_fixture__trails");
  });

  it("words a dbt test's value as the rows it failed or warned on, and a phone file's columns that do not match", () => {
    // `value` is a dbt test's failures, the rows its query returned (macros/data_quality.sql), never a measurement.
    const file = examples.monthlyWithWarnings();
    const base = { column: "id", expected_min: null, expected_max: null, since: null, metric: null };
    file.needs_a_look = [
      { ...base, kind: "dbt_tests", table: "trail_lines", status: "fail", value: 13 },
      { ...base, kind: "dbt_tests", table: "closures", status: "warn", value: 1 },
      { ...base, kind: "dbt_tests", table: "warnings", status: "warn", value: 1204 },
      { ...base, kind: "schema", table: "trail_lines_v2", column: null, status: "warn", value: 2 },
      { ...base, kind: "dbt_tests", table: "places", status: "fail", value: null },
    ];
    const view = page(read(file, "monthly"), MISSING);
    expect(view.sections.items.map((item) => item.sentence)).toEqual([
      "A dbt test on it failed on 13 rows at this build.",
      "A dbt test on it failed.",
      "A dbt test on it warned on 1 row at this build.",
      "A dbt test on it warned on 1,204 rows at this build.",
      "2 columns a phone file reads are missing or not the type it declares, at this build.",
    ]);
    expect(view.sections.items.some((item) => item.sentence.includes("Measured"))).toBe(false);
    expect(tile(view, "dbt_tests").note).toEqual([{ code: "trail_lines" }, ": a dbt test failed on 13 rows.", " And 3 more below."]);
    expect(tile(view, "schema").note).toEqual([{ code: "trail_lines_v2" }, ": 2 columns a phone file reads do not match.", ""]);
  });

  it("prints a value bare when the file does not say what it measures", () => {
    const file = examples.monthlyWithWarnings();
    const { metric, ...unnamed } = file.needs_a_look[1];
    expect(metric).toBe("null_percent");
    file.needs_a_look = [{ ...unnamed, value: 12, expected_min: 0, expected_max: 3 }];
    const [item] = page(read(file, "monthly"), MISSING).sections.items;
    // An entry that names no metric has no history to take a range from the builds before out of.
    expect(item.sentence).toBe(
      "Measured 12 at this build, with no range from the builds before to compare it with. Elementary flagged it above its own range, which counts this build.",
    );
  });

  it("shows a failed or unrunnable check on the card, and says when the counts and the list disagree", () => {
    const file = examples.monthlyAllGreen();
    file.totals = { ...file.totals, passed: file.totals.passed - 3, failed: 2, errored: 1 };
    const view = page(read(file, "monthly"), MISSING);
    expect(view.cards[0].pills.slice(2)).toEqual([
      { tone: "bad", text: "2 failed" },
      { tone: "bad", text: "1 could not run" },
    ]);
    expect(view.sections.quiet).toBe("3 checks need a look by the counts above, and the file lists none of them.");
  });

  it("moves every figure with the file's, because none of them is its own", () => {
    const file = examples.monthlyAllGreen();
    file.kinds = file.kinds.map((k) => (k.kind === "volume" ? { ...k, checks: 7331, passed: 7330, warned: 1 } : k));
    const view = page(read(file, "monthly"), MISSING);
    expect(tile(view, "volume").figure).toEqual({ passed: "7,330", checks: "7,331" });
    expect(texts(tile(view, "volume").pills)).toEqual(["1 unusual"]);
  });

  it("gives no age it would have to guess, when the visitor's clock is behind the build's", () => {
    const view = page(MISSING, read(examples.hourlyAllGreen(), "hourly"), new Date("2026-10-07T22:00:00Z"));
    expect(view.cards[1].meta).toBe("Trail conditions, rebuilt every hour · last run 7 Oct 2026, 23:05 UTC");
  });
});

/** The page drawn from the invented many-problems pair: 43 entries, 38 series, 11 marts. */
const manyView = () => page(read(examples.monthlyManyProblems(), "monthly"), read(examples.hourlyManyProblems(), "hourly"));
const FAILING = new Set(["Failed", "Could not run"]);

describe("Needs a look, listed and folded (round 3's option D)", () => {
  it("opens a kind of 3 warnings by itself and keeps a kind of 4 folded - the maintainer's figure", () => {
    expect(OPEN_FOLD_MAX).toBe(3);
    const monthly = examples.monthlyManyProblems();
    const kept = { schema: 3, anomalies: 4 };
    const seen = { schema: 0, anomalies: 0 };
    monthly.needs_a_look = monthly.needs_a_look.filter((entry) => {
      if (entry.status !== "warn" || !(entry.kind in kept)) return true;
      seen[entry.kind] += 1;
      return seen[entry.kind] <= kept[entry.kind];
    });
    const { folded } = page(read(monthly, "monthly"), MISSING).sections.look.warnings;
    expect(folded.map((group) => [group.kind, group.items.length, group.open])).toEqual([
      ["freshness", 5, false],
      ["volume", 12, false],
      ["schema", 3, true],
      ["anomalies", 4, false],
    ]);
    const light = page(read(examples.monthlyWithWarnings(), "monthly"), MISSING).sections.look.warnings;
    expect(light.folded.every((group) => group.open)).toBe(true);
  });

  it("never folds what failed, what could not run, or a status it does not know - whatever else is in the list", () => {
    const monthly = examples.monthlyManyProblems();
    // A failure of a kind that also has warnings, so it would share their fold if anything folded it.
    monthly.needs_a_look.push(
      { kind: "volume", table: "preview_fixture_40__trails", column: null, metric: "row_count", status: "fail", value: 3, expected_min: 90, expected_max: 110, since: null },
      { kind: "schema", table: "preview_fixture_41__trails", column: "kind", metric: null, status: "skipped", value: null, expected_min: null, expected_max: null, since: null },
    );
    for (const view of [manyView(), page(read(monthly, "monthly"), read(examples.hourlyManyProblems(), "hourly"))]) {
      const { look, items } = view.sections;
      const folded = look.warnings.folded.flatMap((group) => group.items);
      expect(folded.every((item) => item.status === "Warned")).toBe(true);
      expect(look.failing.items.every((item) => FAILING.has(item.status))).toBe(true);
      expect(items.filter((item) => FAILING.has(item.status))).toEqual(look.failing.items);
      // Every entry is drawn once: listed, other, or in one fold.
      expect([...look.failing.items, ...look.other.items, ...folded].map((item) => item.id).sort()).toEqual(
        items.map((item) => item.id).sort(),
      );
    }
    const withSkipped = page(read(monthly, "monthly"), MISSING).sections.look;
    expect(withSkipped.other.items.map((item) => [item.status, item.table])).toEqual([["Skipped", "preview_fixture_41__trails"]]);
    expect(withSkipped.failing.items.at(0)).toMatchObject({ status: "Failed", table: "trail_lines" });
    expect(withSkipped.failing.items.map((item) => item.table)).toContain("preview_fixture_40__trails");
  });

  it("folds the warnings one line per kind, in the five kinds' order, each saying how many it holds", () => {
    const { look } = manyView().sections;
    expect(look.failing.title).toBe("Failed or could not run · 8");
    expect(look.warnings.title).toBe("Warnings · 35, by kind");
    expect(look.warnings.folded.map((group) => [group.kind, group.summary])).toEqual([
      ["freshness", "8 warnings"],
      ["volume", "14 warnings"],
      ["schema", "6 warnings"],
      ["anomalies", "7 warnings"],
    ]);
    const light = page(read(examples.monthlyWithWarnings(), "monthly"), MISSING).sections.look;
    expect(light.failing.items).toEqual([]);
    expect(light.warnings.folded.map((group) => group.summary)).toEqual(["1 warning", "1 warning", "1 warning"]);
  });
});

describe("the Show menu", () => {
  const optionLabels = (group) => group.options.map((option) => option.label);

  it("lists the entries' histories under Needs a look, worst first, then every other mart under Every mart, in By mart's order", () => {
    const { menu, chart } = manyView().sections;
    expect(menu.map((group) => group.label)).toEqual(["Needs a look", "Every mart"]);
    const [look, marts] = menu;
    expect(look.options[0]).toEqual({ key: chart.key, label: "Null rate of trail_status in trail_lines · Monthly" });
    expect(optionLabels(look).slice(1, 3)).toEqual([
      "Rows in preview_fixture_07__water_sources · Monthly",
      "Rows in preview_fixture_03__trails · Monthly",
    ]);
    expect(optionLabels(marts)).toEqual([
      "Rows in trail_network · Monthly",
      "Rows in elevation · Monthly",
      "Rows in places · Monthly",
      "Rows in suggested_hikes · Monthly",
      "Rows in challenges · Monthly",
      "Rows in podcasts · Monthly",
      "Rows in sources · Monthly",
      "Rows in closures · Hourly",
    ]);
  });

  it("lists every series once, and a mart whose row count needs a look under Needs a look alone", () => {
    const { menu, charts } = manyView().sections;
    const keys = menu.flatMap((group) => group.options.map((option) => option.key));
    expect(new Set(keys).size).toBe(keys.length);
    expect(new Set(keys)).toEqual(new Set(charts.keys()));
    const [look, marts] = menu;
    expect(optionLabels(look)).toContain("Rows in trail_lines · Monthly");
    expect(optionLabels(marts)).not.toContain("Rows in trail_lines · Monthly");
  });

  it("works the two groups out from the entries when the file does not flag its series", () => {
    const strip = (file) => ({ ...file, series: file.series.map(({ in_needs_a_look, ...rest }) => rest) });
    const unflagged = page(
      read(strip(examples.monthlyManyProblems()), "monthly"),
      read(strip(examples.hourlyManyProblems()), "hourly"),
    ).sections.menu;
    expect(unflagged).toEqual(manyView().sections.menu);
    const older = page(read(examples.monthlyWithWarnings(), "monthly"), MISSING).sections.menu;
    expect(older).toEqual([
      { label: "Needs a look", options: [{ key: expect.any(String), label: "Rows in preview_fixture__trails · Monthly" }] },
    ]);
  });

  it("opens on the worst entry's own history, and on the first mart's row count when nothing needs a look", () => {
    expect(manyView().sections.chart.title).toEqual([
      "Null rate of ",
      { code: "trail_status" },
      " in ",
      { code: "trail_lines" },
      ", one point per monthly build",
    ]);
    const quiet = examples.monthlyManyProblems();
    quiet.needs_a_look = [];
    quiet.series = quiet.series.filter((s) => !s.in_needs_a_look);
    const { chart, menu, items } = page(read(quiet, "monthly"), MISSING).sections;
    expect(items).toEqual([]);
    expect(chart.table).toBe("trail_network");
    expect(menu.map((group) => group.label)).toEqual(["Every mart"]);
  });
});

describe("the band and the triangles on the heavy files (decision 118)", () => {
  it("flags the newest point of every history a warned or failed entry reports, and no point of a mart's own row count", () => {
    const { charts } = manyView().sections;
    for (const [file, lane] of [
      [examples.monthlyManyProblems(), "monthly"],
      [examples.hourlyManyProblems(), "hourly"],
    ]) {
      for (const series of file.series) {
        const chart = charts.get(seriesKey({ ...series, lane }));
        const flagged = chart.points.flatMap((point, i) => (point.outside ? [i] : []));
        expect(flagged, `${lane} ${series.table} ${series.metric}`).toEqual(series.in_needs_a_look ? [series.points.length - 1] : []);
      }
    }
  });

  it("names the hourly lane's runs in an hourly chart's caption", () => {
    const { charts } = manyView().sections;
    const hourly = [...charts.values()].find((chart) => chart.lane === "hourly");
    expect(hourly.caption).toContain("the range Elementary expected from the hourly runs before it");
    expect(hourly.caption).toContain("none can be flagged before its check has 11 hourly runs.");
  });
});

describe("the range a Needs a look row quotes (decision 130)", () => {
  /** The light monthly page, with `change` made to its file first. */
  const lightPage = (change = () => {}) => {
    const file = examples.monthlyWithWarnings();
    change(file);
    return page(read(file, "monthly"), MISSING);
  };
  const NO_RANGE_BEFORE = "with no range from the builds before to compare it with.";

  it('quotes the band the chart draws at the flagged point, "below the 5,199 to 5,322 expected from the builds before", not Elementary\'s 4,174 to 6,156', () => {
    const view = lightPage();
    const [entry] = examples.monthlyWithWarnings().needs_a_look;
    expect([entry.expected_min, entry.expected_max]).toEqual([4174, 6156]);
    const { items, chart } = view.sections;
    expect(items[0].sentence).toBe("4,118 rows at this build, below the 5,199 to 5,322 expected from the builds before.");
    expect(chart.points.at(-1)).toMatchObject({ value: 4118, min: 5199, max: 5322, outside: "below" });
    expect(chart.rows.at(-1).expected).toBe("5,199 to 5,322, flagged below");
    expect(tile(view, "volume").note).toEqual([{ code: "preview_fixture__trails" }, ": 4,118 rows, below its expected range.", ""]);
  });

  it("quotes, on every heavy-file row with a history, the band its chart draws at the point Elementary flagged", () => {
    const { items, charts } = manyView().sections;
    const charted = items.filter((item) => item.chart !== null);
    expect(charted).toHaveLength(30);
    for (const item of charted) {
      const chart = charts.get(item.chart);
      const point = chart.points.findLast((candidate) => candidate.outside !== null);
      expect(item.sentence, item.id).toContain(
        `, ${point.outside} the ${chart.format.range(point.min, point.max)} expected from the builds before.`,
      );
      expect(item.sentence, item.id).not.toContain("its own range");
    }
  });

  it('says "with no range from the builds before" when the file holds no history of the entry, and gives Elementary\'s side', () => {
    const view = lightPage((file) => (file.series = []));
    const [row] = view.sections.items;
    expect(row.chart).toBeNull();
    expect(row.sentence).toBe(
      `4,118 rows at this build, ${NO_RANGE_BEFORE} Elementary flagged it below its own range, which counts this build.`,
    );
    // The card names no side against a range the page cannot show.
    expect(tile(view, "volume").note[1]).toBe(": 4,118 rows, flagged by Elementary.");
  });

  it('says "with no range from the builds before" when the entry\'s history holds no point with its value and range', () => {
    // The history is there and charted, but no point of it is this entry's, so no band before it can be named.
    const view = lightPage((file) => (file.needs_a_look[0].value = 4117));
    const [row] = view.sections.items;
    expect(row.chart).not.toBeNull();
    expect(row.sentence).toBe(
      `4,117 rows at this build, ${NO_RANGE_BEFORE} Elementary flagged it below its own range, which counts this build.`,
    );
  });

  it('says "with no range from the builds before" when the point before the flagged one has no band, as the chart\'s table says "No range" there', () => {
    const view = lightPage((file) => {
      const before = file.series[0].points.at(-2);
      before.expected_min = null;
      before.expected_max = null;
    });
    const { items, chart } = view.sections;
    expect(chart.rows.at(-1).expected).toBe(`${NO_RANGE}, flagged below`);
    expect(items[0].sentence).toBe(
      `4,118 rows at this build, ${NO_RANGE_BEFORE} Elementary flagged it below its own range, which counts this build.`,
    );
  });

  it('says "inside the 4,000 to 5,322 expected from the builds before" for a value Elementary flagged, then the side of its own range it flagged', () => {
    const view = lightPage((file) => (file.series[0].points.at(-2).expected_min = 4000));
    const { items, chart } = view.sections;
    expect(items[0].sentence).toBe(
      "4,118 rows at this build, inside the 4,000 to 5,322 expected from the builds before. Elementary flagged it below its own range, which counts this build.",
    );
    // The row and its triangle are still Elementary's verdict.
    expect(items[0].status).toBe("Warned");
    expect(chart.points.at(-1)).toMatchObject({ min: 4000, max: 5322, outside: "below" });
    expect(tile(view, "volume").note[1]).toBe(": 4,118 rows, flagged by Elementary.");
  });

  it("gives Elementary's side in a second sentence when the range from the builds before puts the value past its other edge", () => {
    const view = lightPage((file) => {
      const before = file.series[0].points.at(-2);
      before.expected_min = 3000;
      before.expected_max = 4000;
    });
    expect(view.sections.items[0].sentence).toBe(
      "4,118 rows at this build, above the 3,000 to 4,000 expected from the builds before. Elementary flagged it below its own range, which counts this build.",
    );
    expect(tile(view, "volume").note[1]).toBe(": 4,118 rows, flagged by Elementary.");
  });
});

describe("Chart buttons", () => {
  it("sit on every entry with a history and on no other", () => {
    const { items } = manyView().sections;
    const charted = items.filter((item) => item.chart !== null);
    expect(charted).toHaveLength(30);
    expect(items.filter((item) => ["dbt tests", "Schema"].includes(item.kind)).every((item) => item.chart === null)).toBe(true);
    expect(items.filter((item) => item.status === "Could not run").every((item) => item.chart === null)).toBe(true);
    expect(charted[0]).toMatchObject({
      table: "trail_lines",
      column: "trail_status",
      chartName: "Chart null rate of trail_status in trail_lines, Monthly",
    });
  });

  it("match a column's history to that column's entry and to no other column's", () => {
    const file = examples.monthlyManyProblems();
    // trail_lines.surface warns with a history; trail_lines.id gains a null-rate warning with none.
    file.needs_a_look.push({ ...file.needs_a_look.find((entry) => entry.column === "surface"), column: "id" });
    const { items } = page(read(file, "monthly"), MISSING).sections;
    const row = (column) => items.find((item) => item.table === "trail_lines" && item.column === column && item.kind === "Anomalies");
    expect(row("surface").chart).toBe(seriesKey({ lane: "monthly", table: "trail_lines", column: "surface", metric: "null_percent" }));
    expect(row("id").chart).toBeNull();
  });

  it("sit on every mart the file holds a row count for, and on none an older file lists", () => {
    const { marts } = manyView().sections;
    expect(marts.every((mart) => mart.chart !== null)).toBe(true);
    expect(marts.map((mart) => mart.id)).toEqual(marts.map((_, i) => `dq-mart-${i}`));
    const older = page(read(examples.monthlyWithWarnings(), "monthly"), MISSING).sections;
    expect(older.marts.every((mart) => mart.chart === null)).toBe(true);
    expect(older.buttons.map((button) => button.from)).toEqual(["Needs a look"]);
  });

  it("find a mart's row count under its versioned table, by the series' mart, as C1's file names them", () => {
    // C1's test-warehouse file, 2026-10-08: `table: "trail_lines_v1", mart: "trail_lines"`, and by_mart says "trail_lines".
    const file = examples.monthlyManyProblems();
    file.series = file.series.map((series) =>
      series.in_needs_a_look ? series : { ...series, table: `${series.table}_v1`, mart: series.table },
    );
    const { marts, menu } = page(read(file, "monthly"), MISSING).sections;
    const network = marts.find((mart) => mart.mart === "trail_network");
    expect(network.chart).toBe(seriesKey({ lane: "monthly", table: "trail_network_v1", metric: "row_count" }));
    expect(network.chartName).toBe("Chart rows in trail_network_v1, Monthly");
    expect(marts.every((mart) => mart.chart !== null)).toBe(true);
    expect(menu[1].options[0].label).toBe("Rows in trail_network_v1 · Monthly");
  });

  it("show a mart's highest version's row count when it has two, in either order, and list both in the menu", () => {
    // trail_lines_v1 is written beside trail_lines_v2 until its deprecation_date (decision 44), and v2 holds v1's
    // rows by an equal_rowcount test; the series the mart's button keeps is the one that outlives the other.
    const file = examples.monthlyManyProblems();
    const rowCount = (series) => series.mart === "trail_network" && series.metric === "row_count" && series.column === null;
    const network = file.series.find(rowCount);
    const versions = (...suffixes) => suffixes.map((suffix) => ({ ...network, table: `trail_network${suffix}` }));
    const v2 = seriesKey({ lane: "monthly", table: "trail_network_v2", metric: "row_count" });
    for (const order of [["_v1", "_v2"], ["_v2", "_v1"]]) {
      file.series = [...file.series.filter((series) => !rowCount(series)), ...versions(...order)];
      const { marts, menu } = page(read(file, "monthly"), MISSING).sections;
      const row = marts.find((mart) => mart.mart === "trail_network");
      expect(row.chart).toBe(v2);
      expect(row.chartName).toBe("Chart rows in trail_network_v2, Monthly");
      const labels = menu.flatMap((group) => group.options.map((option) => option.label));
      expect(labels).toEqual(expect.arrayContaining(["Rows in trail_network_v1 · Monthly", "Rows in trail_network_v2 · Monthly"]));
    }
  });

  it("join a mart's row by the series' mart alone, never by a table that merely shares its name", () => {
    const file = examples.monthlyManyProblems();
    // trail_network's own row count, its table named as the mart is, but its `mart` null: no mart's.
    file.series = file.series.map((series) =>
      series.mart === "trail_network" && series.metric === "row_count" ? { ...series, mart: null } : series,
    );
    const { marts } = page(read(file, "monthly"), MISSING).sections;
    expect(marts.find((mart) => mart.mart === "trail_network").chart).toBeNull();
    expect(marts.filter((mart) => mart.chart === null).map((mart) => mart.mart)).toEqual(["trail_network"]);
  });
});

describe("the menu and the buttons, in step", () => {
  const sections = () => manyView().sections;
  const rowOf = (s, table, kind) => s.items.find((item) => item.table === table && item.kind === kind).id;

  it("open with the first chart's own row pressed, the menu on its series, and the line naming that row", () => {
    const s = sections();
    const shown = chartControls(s, initialChart(s));
    // pickSeries took the first chart from the worst entry with a history: the failed null-rate check.
    const opening = s.items.find((item) => item.id === s.opening);
    expect(opening).toMatchObject({ status: "Failed", table: "trail_lines", column: "trail_status", chart: s.chart.key });
    expect(s.items.findIndex((item) => item.chart !== null)).toBe(s.items.indexOf(opening));
    expect(shown.selected).toBe(s.chart.key);
    expect(shown.chart).toBe(s.chart);
    expect(shown.pressed).toEqual([opening.id]);
    expect(shown.charted).toEqual({ from: "Needs a look", table: "trail_lines", column: "trail_status", row: opening.id });
  });

  it("open with a warning's row pressed inside its closed fold, when the first chart is a warning's", () => {
    const monthly = examples.monthlyManyProblems();
    monthly.series = monthly.series.filter((series) => series.column !== "trail_status");
    const s = page(read(monthly, "monthly"), read(examples.hourlyManyProblems(), "hourly")).sections;
    const shown = chartControls(s, initialChart(s));
    const volume = s.look.warnings.folded.find((group) => group.kind === "volume");
    expect(volume.open).toBe(false);
    expect(volume.items.map((item) => item.id)).toContain(s.opening);
    expect(s.items.find((item) => item.id === s.opening).table).toBe("preview_fixture_07__water_sources");
    expect(shown.pressed).toEqual([s.opening]);
    expect(shown.charted).toMatchObject({ from: "Needs a look", table: "preview_fixture_07__water_sources" });
  });

  it("open with the first mart's row pressed when nothing needs a look, and with none when no button draws the first chart", () => {
    const quiet = examples.monthlyManyProblems();
    quiet.needs_a_look = [];
    quiet.series = quiet.series.filter((series) => !series.in_needs_a_look);
    const s = page(read(quiet, "monthly"), MISSING).sections;
    const mart = s.marts.find((row) => row.mart === "trail_network");
    expect(chartControls(s, initialChart(s))).toMatchObject({
      pressed: [mart.id],
      charted: { from: "By mart", table: "trail_network", row: mart.id },
    });
    const unmatched = examples.monthlyWithWarnings();
    unmatched.needs_a_look = [];
    const lone = page(read(unmatched, "monthly"), MISSING).sections;
    expect(lone.chart.table).toBe("preview_fixture__trails");
    expect(chartControls(lone, initialChart(lone))).toMatchObject({ pressed: [], charted: null });
  });

  it("release the opening press when another row's button is pressed, and when the menu chooses another series", () => {
    const s = sections();
    const other = s.items.find((item) => item.table === "preview_fixture_12__shelters" && item.kind === "Volume");
    expect(chartControls(s, chooseFromRow(s, other.id)).pressed).toEqual([other.id]);
    const elsewhere = s.menu[1].options[0].key;
    expect(chartControls(s, chooseFromMenu(elsewhere))).toMatchObject({ selected: elsewhere, pressed: [], charted: null });
  });

  it("set the menu from a pressed button, press that row alone, and name it above the chart", () => {
    const s = sections();
    const row = rowOf(s, "preview_fixture_12__shelters", "Volume");
    const shown = chartControls(s, chooseFromRow(s, row));
    expect(shown.selected).toBe(seriesKey({ lane: "monthly", table: "preview_fixture_12__shelters", metric: "row_count" }));
    expect(shown.chart.table).toBe("preview_fixture_12__shelters");
    expect(shown.pressed).toEqual([row]);
    expect(shown.charted).toEqual({ from: "Needs a look", table: "preview_fixture_12__shelters", column: null, row });
  });

  it("clear a pressed button when the menu chooses another series", () => {
    const s = sections();
    const pressed = chooseFromRow(s, rowOf(s, "preview_fixture_12__shelters", "Volume"));
    const other = s.menu[1].options[0].key;
    const shown = chartControls(s, chooseFromMenu(other));
    expect(chartControls(s, pressed).pressed).toHaveLength(1);
    expect(shown.selected).toBe(other);
    expect(shown.chart.table).toBe("trail_network");
    expect(shown.pressed).toEqual([]);
    expect(shown.charted).toBeNull();
  });

  it("press a mart's row from By mart, and the row of the series the page opened on when its own button is pressed", () => {
    const s = sections();
    const mart = s.marts.find((row) => row.mart === "trail_network");
    expect(chartControls(s, chooseFromRow(s, mart.id))).toMatchObject({
      pressed: [mart.id],
      charted: { from: "By mart", table: "trail_network", row: mart.id },
    });
    const opening = s.items.find((item) => item.chart === s.chart.key);
    const shown = chartControls(s, chooseFromRow(s, opening.id));
    expect(shown.selected).toBe(s.chart.key);
    expect(shown.pressed).toEqual([opening.id]);
  });

  it("change nothing for a row with no Chart button", () => {
    const s = sections();
    expect(chooseFromRow(s, rowOf(s, "closures", "dbt tests"))).toBeNull();
  });
});

describe("formatting", () => {
  it("writes counts with thousands separators", () => {
    expect([0, 7, 3412, 1234567].map(formatCount)).toEqual(["0", "7", "3,412", "1,234,567"]);
  });

  it("writes other numbers to a precision that fits their size", () => {
    expect([4.2, 0.004, 12.345, 100.4, -3.5, 1500.25].map(formatNumber)).toEqual([
      "4.2",
      "0.004",
      "12.3",
      "100",
      "-3.5",
      "1,500",
    ]);
  });

  it("writes seconds as the duration a person reads", () => {
    expect([45, 600, 3600, 5400, 93600, 259200].map(formatDuration)).toEqual([
      "45 seconds",
      "10 minutes",
      "1 hour",
      "1.5 hours",
      "26 hours",
      "3 days",
    ]);
  });

  it("writes a range in one unit, unless its lower end would read as a fraction of it", () => {
    expect(formatDurationRange(3600, 43200)).toBe("1 to 12 hours");
    expect(formatDurationRange(0, 43200)).toBe("0 to 12 hours");
    expect(formatDurationRange(600, 43200)).toBe("10 minutes to 12 hours");
  });

  it("writes an instant in UTC, the same in every browser", () => {
    expect(formatWhen(new Date("2026-10-07T06:12:00Z"))).toBe("7 Oct 2026, 06:12 UTC");
    expect(formatWhen(new Date("2026-01-02T23:05:59Z"))).toBe("2 Jan 2026, 23:05 UTC");
  });

  it("writes an age, and none from a clock more than five minutes behind", () => {
    const at = new Date("2026-10-08T00:00:00Z");
    const after = (ms) => formatAge(at, new Date(at.getTime() + ms));
    expect(after(30_000)).toBe("just now");
    expect(after(-120_000)).toBe("just now");
    expect(after(60_000)).toBe("1 minute ago");
    expect(after(40 * 60_000)).toBe("40 minutes ago");
    expect(after(13 * 3_600_000)).toBe("13 hours ago");
    expect(after(3 * 86_400_000)).toBe("3 days ago");
    expect(after(-10 * 60_000)).toBeNull();
  });
});
