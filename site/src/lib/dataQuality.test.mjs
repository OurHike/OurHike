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
  configFrom,
  formatAge,
  formatCount,
  formatDuration,
  formatDurationRange,
  formatNumber,
  formatWhen,
  laneUrl,
  readQualityFile,
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
    expect(view.cards[0].learning.text).toBe("Learning, 3 of 7 builds");
    expect(view.cards[0].learning.detail).toContain("wait for 7");
    for (const id of ["freshness", "volume", "anomalies"]) {
      expect(tile(view, id).learning).toBe(
        "Learning, 3 of 7 monthly builds: until then a pass may only mean an anomaly check cannot fire yet.",
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
      expect(rows).toBe(
        `4,118 rows at this build, below the ${formatCount(volume.expected_min)} to ${formatCount(volume.expected_max)} Elementary expected.`,
      );
      expect(nulls).toBe("Null rate: 4.2% at this build, above the 0% to 1.5% Elementary expected.");
      expect(columns).toBe("Its columns no longer match what Elementary expected.");
      expect(late).toBe("26 hours between updates at this build, above the 10 minutes to 12 hours Elementary expected.");
      expect(view.sections.items.map((item) => item.since)).toEqual([
        "Since this build",
        "Since 7 Sep 2026, 06:12 UTC",
        "Since this build",
        "Since 6 Oct 2026, 21:05 UTC",
      ]);
    });

    it("draws the history behind the worst entry that has one, banded where Elementary had enough to expect", () => {
      const { chart } = view.sections;
      expect(chart.table).toBe("preview_fixture__trails");
      expect(chart.rows).toHaveLength(monthly.series[0].points.length);
      expect(chart.rows.at(-1)).toMatchObject({
        when: "7 Oct 2026",
        value: "4,118",
        expected: `${formatCount(volume.expected_min)} to ${formatCount(volume.expected_max)}, below it`,
        where: "Below the range",
      });
      expect(chart.rows[0].expected).toBe("No range yet");
      expect(chart.summary).toBe(
        "12 monthly builds, from 5,231 on 7 Nov 2025 to 4,118 on 7 Oct 2026. 1 of them falls outside the range Elementary expected.",
      );
      expect(chart.caption).toContain("the 7 earlier monthly builds it waits for");
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

  it("prints a value bare when the file does not say what it measures", () => {
    const file = examples.monthlyWithWarnings();
    const { metric, ...unnamed } = file.needs_a_look[1];
    expect(metric).toBe("null_percent");
    file.needs_a_look = [{ ...unnamed, value: 12, expected_min: 0, expected_max: 3 }];
    const [item] = page(read(file, "monthly"), MISSING).sections.items;
    expect(item.sentence).toBe("Measured 12 at this build, above the 0 to 3 Elementary expected.");
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
