// The two counts "How the data is built" (/data/how/) prints, worked out from
// the repository when the site is built (Q24 of #1805 — dlt → dbt re-platform
// as one go/no-go change: "figures must come from data", the lead's brief of
// the maintainer's "All three as drawn", 2026-10-15). Measured, not typed:
// the page's numbers are whatever the checkout it was built from holds, so
// they cannot go stale against the code beside them.
//
// Null where the directory cannot be read, and the page then prints the
// sentence without the number rather than a remembered one.

import { readdirSync } from "node:fs";
import { join } from "node:path";

/**
 * The organizations OurHike gathers from: pipeline/extract/'s folders, one
 * per organization or shared source by the folder contract
 * (.claude/skills/dlt/SKILL.md), less the `_` helpers beside them.
 */
export function countSourceFolders(extractDir) {
  try {
    return readdirSync(extractDir, { withFileTypes: true }).filter(
      (entry) => entry.isDirectory() && !entry.name.startsWith("_") && !entry.name.startsWith("."),
    ).length;
  } catch {
    return null;
  }
}

/** The dbt models: every .sql file under pipeline/dbt/models/. */
export function countModels(modelsDir) {
  const walk = (dir) =>
    readdirSync(dir, { withFileTypes: true }).reduce(
      (n, entry) =>
        n + (entry.isDirectory() ? walk(join(dir, entry.name)) : entry.name.endsWith(".sql") ? 1 : 0),
      0,
    );
  try {
    return walk(modelsDir);
  } catch {
    return null;
  }
}
