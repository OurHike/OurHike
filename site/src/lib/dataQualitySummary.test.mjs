// The summary at the top of /data/quality/ (Q24 of #1805 — dlt → dbt
// re-platform as one go/no-go change), from INVENTED files in the contract's
// shape: every organization and source key here is an example, none is a
// real steward's.

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { readQualityFile } from "./dataQuality.mjs";
import { renderSummary } from "./dataQualityHtml.mjs";
import { buildSummary, MART_LABELS, orgOfTable, providersByKey } from "./dataQualitySummary.mjs";

const blank = (column, status = "fail") => ({
  kind: "anomalies",
  table: "closures_v1",
  column,
  status,
  value: 30,
  expected_min: 10,
  expected_max: 25,
  since: "2026-10-15T16:31:02Z",
  metric: "null_percent",
  test: "all_columns_anomalies",
});
const rows = (table, status) => ({
  kind: "volume",
  table,
  column: null,
  status,
  value: 4,
  expected_min: 0,
  expected_max: 3.5,
  since: "2026-10-14T18:21:51Z",
  metric: "row_count",
  test: "volume_anomalies",
});

function hourly() {
  return {
    format: "ourhike-data-quality/1",
    lane: "hourly",
    built_at: "2026-10-15T20:49:41Z",
    totals: { checks: 200, passed: 189, warned: 4, failed: 7, errored: 0 },
    kinds: [],
    learning: { builds: 72, needed: 11 },
    needs_a_look: [
      blank("category"),
      blank("ends_on"),
      blank("title"),
      { ...blank(null), metric: "dimension", test: "dimension_anomalies", expected_min: null, expected_max: null },
      { ...blank(null), table: "warnings_v1", metric: "dimension", test: "dimension_anomalies", expected_min: null, expected_max: null },
      rows("raw_example_club__example_alerts", "fail"),
      rows("closures_v1", "warn"),
      rows("raw_example_agency__example_orders", "warn"),
      rows("raw_example_agency__example_perimeters", "warn"),
      rows("raw_unlisted_folder__unlisted_key", "warn"),
    ],
    series: [],
    by_mart: [
      { mart: "sources", checks: 5, passed: 5, warned: 0, failed: 0, errored: 0 },
      { mart: "warnings", checks: 80, passed: 79, warned: 0, failed: 1, errored: 0 },
      { mart: "closures", checks: 83, passed: 78, warned: 1, failed: 4, errored: 0 },
    ],
  };
}

function monthly() {
  return {
    format: "ourhike-data-quality/1",
    lane: "monthly",
    built_at: "2026-10-10T11:56:56Z",
    totals: { checks: 600, passed: 597, warned: 2, failed: 0, errored: 1 },
    kinds: [],
    learning: { builds: 2, needed: 11 },
    needs_a_look: [],
    series: [],
    by_mart: [
      { mart: "trail_lines", checks: 285, passed: 283, warned: 2, failed: 0, errored: 0 },
      { mart: "points_of_interest", checks: 160, passed: 160, warned: 0, failed: 0, errored: 0 },
      { mart: "elevation", checks: 72, passed: 71, warned: 0, failed: 0, errored: 1 },
      { mart: "a_new_mart", checks: 3, passed: 3, warned: 0, failed: 0, errored: 0 },
    ],
  };
}

const ok = (file, lane) => {
  const read = readQualityFile(file, lane);
  if (!read.ok) throw new Error(read.why);
  return { state: "ok", file: read.file };
};

const PROVIDERS = {
  example_alerts: "Example Trail Club",
  example_orders: "Example Agency",
  example_perimeters: "Example Agency",
};

const summary = () =>
  buildSummary({
    lanes: { hourly: ok(hourly(), "hourly"), monthly: ok(monthly(), "monthly") },
    providers: PROVIDERS,
    release: "2026-10-10-2",
  });

describe("the summary at the top of the quality page", () => {
  it("draws nothing until a file is read", () => {
    expect(buildSummary({ lanes: { hourly: { state: "loading" }, monthly: { state: "missing" } } })).toBeNull();
    expect(renderSummary(null)).toBe("");
  });

  it("lists what is on the map, hourly first, each lane in the map's order, a mart it has no words for by its own name", () => {
    expect(summary().rows.map((row) => [row.label ?? row.rest, row.when])).toEqual([
      ["Closures", "hourly conditions, last built 15 Oct, 20:49 UTC"],
      ["Warnings", "hourly conditions, last built 15 Oct, 20:49 UTC"],
      // A mart that is not one a hiker acts on, with nothing flagged, shares
      // one line per lane with the lane's other clean ones.
      [["Credits to each organization"], "hourly conditions, last built 15 Oct, 20:49 UTC"],
      ["Trail lines", "monthly build, release 2026-10-10-2"],
      ["Shelters, water and other waypoints", "monthly build, release 2026-10-10-2"],
      // Flagged: a row of its own, even though it is not one a hiker acts on.
      ["Elevation", "monthly build, release 2026-10-10-2"],
      [["a_new_mart"], "monthly build, release 2026-10-10-2"],
    ]);
    expect(summary().rows.at(-1).status.map((part) => part.text)).toEqual(["nothing failed", "all 3 checks passed"]);
    expect(renderSummary(summary())).toContain("<strong>Everything else</strong> · monthly build, release 2026-10-10-2: a_new_mart");
    expect(Object.keys(MART_LABELS)).toContain("trail_network");
  });

  it("says what failed and warned in words, and 'nothing failed' only where nothing failed or could not run", () => {
    const words = Object.fromEntries(summary().rows.map((row) => [row.mart ?? row.id, row.status.map((part) => part.text)]));
    expect(words.closures).toEqual(["4 checks failed", "1 warned"]);
    expect(words.warnings).toEqual(["1 check failed"]);
    expect(words["hourly-rest"]).toEqual(["nothing failed", "all 5 checks passed"]);
    expect(words.trail_lines).toEqual(["nothing failed", "2 warnings"]);
    expect(words.elevation).toEqual(["1 could not run"]);
    const html = renderSummary(summary());
    expect(html).toContain("4 checks failed");
    expect(html).not.toMatch(/Closures<\/strong>[^<]*<\/p>\s*<p class="dq-sum__status"><span class="dq-sum__ok">nothing failed/);
  });

  it("says what most of a mart's failures are when they are blank columns, naming the columns from the file", () => {
    const closures = summary().rows.find((row) => row.mart === "closures");
    expect(closures.mostly).toEqual({
      text: "3 of the 4 are a column blank more often than usual:",
      columns: ["category", "ends_on", "title"],
    });
    expect(summary().rows.find((row) => row.mart === "warnings").mostly).toBeNull();
    expect(renderSummary(summary())).toContain('<a href="#dq-look-title">See which ↓</a>');
  });

  it("names organizations only where one of their feeds was flagged, by provider, or by folder where the key is not listed", () => {
    expect(summary().orgs).toEqual([
      {
        lane: "hourly",
        when: "this hour",
        flagged: [
          { org: "Example Trail Club", failed: 1, warned: 0 },
          { org: "Example Agency", failed: 0, warned: 2 },
          { org: "unlisted_folder", failed: 0, warned: 1 },
        ],
      },
    ]);
    const html = renderSummary(summary());
    expect(html).toContain(
      "checks flagged a feed from 3 organizations: Example Trail Club (1 failed); Example Agency (2 warned); unlisted_folder (1 warned).",
    );
    expect(html).toContain("does not yet count checks per organization");
  });

  it("reads a raw table's organization off its name, and no other table's", () => {
    expect(orgOfTable("raw_example_club__example_alerts", PROVIDERS)).toBe("Example Trail Club");
    expect(orgOfTable("raw_x__y", PROVIDERS)).toBe("x");
    expect(orgOfTable("closures_v1", PROVIDERS)).toBeNull();
    expect(orgOfTable("base_blm__trails", PROVIDERS)).toBeNull();
  });

  it("reads providers from pipeline/sources.json as committed", () => {
    const sources = JSON.parse(readFileSync(join(import.meta.dirname, "../../../pipeline/sources.json"), "utf8"));
    const providers = providersByKey(sources);
    expect(Object.keys(providers).length).toBeGreaterThan(100);
    expect(providers.centerline).toBe("ATC");
    expect(providersByKey(null)).toEqual({});
  });

  it("escapes what it prints from the files", () => {
    const file = hourly();
    file.by_mart = [{ mart: "<b>x</b>", checks: 1, passed: 0, warned: 1, failed: 0, errored: 0 }];
    file.needs_a_look = [rows("raw_a__k", "warn")];
    const html = renderSummary(
      buildSummary({ lanes: { hourly: ok(file, "hourly") }, providers: { k: "<script>" } }),
    );
    expect(html).not.toContain("<b>x</b>");
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
  });
});
