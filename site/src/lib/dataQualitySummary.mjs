// The block at the top of /data/quality/: how the last build of each thing on
// the map went, in a hiker's words, then by organization (#1805 — dlt →
// dbt re-platform as one go/no-go change: the maintainer chose "All three as
// drawn", 2026-10-15, from q24_frames.html). Pure, like dataQuality.mjs: it
// takes the files that module read and returns what to print.
//
// EVERY FIGURE IS THE FILE'S. A row's counts are its `by_mart` entry; "what
// most of them are" is read off `needs_a_look`; the organizations are read off
// the names of the flagged `raw_<folder>__<source key>` tables, named through
// pipeline/sources.json's `provider` for that key. What is written here rather
// than read is only the label each mart gets (MART_LABELS).
//
// NEVER "NOTHING FAILED" WHEN SOMETHING DID, and never a clean line for a
// check that could not run: a row says "nothing failed" only when its file
// counts no failure and no error.
//
// ORGANIZATIONS ONLY WHERE A TABLE IS FLAGGED. The file counts checks per
// mart, not per source, so an organization whose feeds passed cannot be named
// from it; the block says so rather than listing them as passing. A full row
// per organization needs data_quality.json to carry counts per source, which
// is a pipeline change (q24_frames.html's note).

/** What each mart is on the map, in a hiker's words, in the order drawn. A
 *  mart the file names that is not here is printed by its own name. */
export const MART_LABELS = {
  closures: "Closures",
  warnings: "Warnings",
  trail_lines: "Trail lines",
  points_of_interest: "Shelters, water and other waypoints",
  places: "Places",
  elevation: "Elevation",
  trail_network: "The trail network seen from far out",
  suggested_hikes: "Suggested hikes",
  challenges: "Challenges",
  podcasts: "Podcasts",
  sources: "Credits to each organization",
};
const ORDER = Object.keys(MART_LABELS);

/** The marts that always get a row of their own, flagged or not, as the
 *  frame drew them: what a hiker acts on. Any other mart gets a row only when
 *  something in it was flagged; the clean ones of a lane share one line. */
export const OWN_ROW = new Set(["closures", "warnings", "trail_lines", "points_of_interest"]);

/** The lanes, in the order the block draws them: the hourly one changes
 *  under a hiker between releases, so it comes first. */
const LANE_ORDER = ["hourly", "monthly"];

const plural = (n, one, many) => (n === 1 ? one : many);
const count = (n) => n.toLocaleString("en-US");

/** `{source key: provider}` from pipeline/sources.json's parsed text: what
 *  the page names a flagged `raw_` table's organization by. */
export function providersByKey(sources) {
  const rows = Array.isArray(sources?.sources) ? sources.sources : [];
  const out = {};
  for (const row of rows) {
    if (typeof row?.key === "string" && typeof row?.provider === "string" && row.provider !== "") {
      out[row.key] = row.provider;
    }
  }
  return out;
}

/**
 * The organization a table's checks are about, or null for a table that is
 * not one source's raw table. `raw_<folder>__<key>` is named by the
 * provider sources.json gives `<key>`, else by its folder as written, which
 * is the file's own word rather than a guess.
 */
export function orgOfTable(table, providers) {
  const match = /^raw_([a-z0-9_]+?)__([a-z0-9_]+)$/.exec(table);
  if (match === null) return null;
  const [, folder, key] = match;
  return providers[key] ?? folder;
}

/** Whether a flagged item is about mart `mart`'s own table (`closures_v1`). */
const ofMart = (item, mart) => item.table === mart || new RegExp(`^${mart}_v\\d+$`).test(item.table);

/** "5 of the 6 are a column blank more often than usual: category, …", or null. */
function mostly(file, mart, failed) {
  if (failed === 0) return null;
  const blanks = file.items.filter(
    (item) => item.status === "fail" && ofMart(item, mart) && item.metric === "null_percent" && item.column,
  );
  if (blanks.length === 0) return null;
  const columns = [...new Set(blanks.map((item) => item.column))];
  const share = blanks.length === failed ? (failed === 1 ? "It is" : `All ${failed} are`) : `${blanks.length} of the ${failed} are`;
  return { text: `${share} a column blank more often than usual:`, columns };
}

/** The status line of one row: what failed and warned, never "nothing failed" when something did. */
function statusOf(c) {
  const parts = [];
  if (c.failed > 0) parts.push({ tone: "bad", text: `${count(c.failed)} ${plural(c.failed, "check", "checks")} failed` });
  if (c.errored > 0) parts.push({ tone: "bad", text: `${count(c.errored)} could not run` });
  if (c.failed > 0 || c.errored > 0) {
    if (c.warned > 0) parts.push({ tone: "warn", text: `${count(c.warned)} warned` });
    return parts;
  }
  if (c.checks === 0) return [{ tone: "neutral", text: "no checks ran" }];
  parts.push({ tone: "ok", text: "nothing failed" });
  parts.push(
    c.warned > 0
      ? { tone: "warn", text: `${count(c.warned)} ${plural(c.warned, "warning", "warnings")}` }
      : { tone: "ok", text: `all ${count(c.checks)} checks passed` },
  );
  return parts;
}

const pad = (n) => String(n).padStart(2, "0");
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const utcDay = (d) => `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;

/** When a lane's file was built, as its row says it. */
function whenOf(file, release) {
  const at = file.builtAt;
  if (file.lane === "hourly") return `hourly conditions, last built ${utcDay(at)}, ${pad(at.getUTCHours())}:${pad(at.getUTCMinutes())} UTC`;
  return release ? `monthly build, release ${release}` : `monthly build of ${utcDay(at)}`;
}

/** The organizations a lane flagged, most failures first. */
function orgsOf(file, providers) {
  const by = new Map();
  for (const item of file.items) {
    const org = orgOfTable(item.table, providers);
    if (org === null) continue;
    const entry = by.get(org) ?? { org, failed: 0, warned: 0 };
    if (item.status === "fail" || item.status === "error") entry.failed += 1;
    else entry.warned += 1;
    by.set(org, entry);
  }
  return [...by.values()].sort((a, b) => b.failed - a.failed || b.warned - a.warned || a.org.localeCompare(b.org));
}

/** "1 failed" / "6 warned" / "1 failed, 2 warned". */
export function orgCounts({ failed, warned }) {
  return [failed > 0 ? `${failed} failed` : null, warned > 0 ? `${warned} warned` : null].filter(Boolean).join(", ");
}

/**
 * The block's view, or null while neither file has been read. `lanes` is
 * `{hourly, monthly}`, each a settled lane ({state: "ok", file} when read);
 * `release` is the monthly file's release id.
 */
export function buildSummary({ lanes, providers = {}, release = null }) {
  const read = LANE_ORDER.filter((lane) => lanes[lane]?.state === "ok").map((lane) => lanes[lane].file);
  if (read.length === 0) return null;
  const rows = [];
  const orgs = [];
  for (const file of read) {
    const marts = [...file.marts].sort((a, b) => {
      const ia = ORDER.indexOf(a.mart);
      const ib = ORDER.indexOf(b.mart);
      return (ia < 0 ? ORDER.length : ia) - (ib < 0 ? ORDER.length : ib) || a.mart.localeCompare(b.mart);
    });
    const clean = [];
    for (const m of marts) {
      const flagged = m.failed + m.warned + m.errored > 0;
      if (!flagged && !OWN_ROW.has(m.mart) && m.checks > 0) {
        clean.push(m);
        continue;
      }
      rows.push({
        id: `${file.lane}-${m.mart}`,
        label: MART_LABELS[m.mart] ?? null,
        mart: m.mart,
        when: whenOf(file, release),
        status: statusOf(m),
        mostly: mostly(file, m.mart, m.failed),
        seeWhich: m.failed + m.warned + m.errored > 0,
      });
    }
    if (clean.length > 0) {
      rows.push({
        id: `${file.lane}-rest`,
        label: null,
        mart: null,
        rest: clean.map((m) => MART_LABELS[m.mart] ?? m.mart),
        when: whenOf(file, release),
        status: [
          { tone: "ok", text: "nothing failed" },
          { tone: "ok", text: `all ${count(clean.reduce((n, m) => n + m.checks, 0))} checks passed` },
        ],
        mostly: null,
        seeWhich: false,
      });
    }
    const flagged = orgsOf(file, providers);
    if (flagged.length > 0) orgs.push({ lane: file.lane, when: file.lane === "hourly" ? "this hour" : "in this release", flagged });
  }
  return {
    title: "What you see on the map, and how its last build went",
    rows,
    orgs,
    orgNote:
      "Organizations are named here only where one of their feeds was flagged: the checks file does not yet count checks per organization, so one whose feeds all passed cannot be named from it.",
  };
}
