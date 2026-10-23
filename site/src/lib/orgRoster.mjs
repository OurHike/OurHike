// The organizations page and the homepage's count (#1877), derived from
// pipeline/sources.json when the site is built rather than typed in.
//
// heroOrgs.mjs's ORGS was the roster until 2026-10-23: five organizations,
// typed by hand on 2026-08-26, while the registry grew to 150. Nothing
// noticed, because nothing read the registry. This does, so the page and the
// count move when the registry does.
//
// EVERY REGISTERED ORGANIZATION IS LISTED - 150 on main at 072fc298 - with
// how many of its sources are `reaches_hikers: true`. A first version listed
// only the 111 with a shipping source; the maintainer's instruction of
// 2026-10-23 was to publish all of them. The 39 with none are listed as
// registered and not yet on the map, never as data sources: a page naming a
// steward whose data does not ship as if it did is "the same category of
// quiet inaccuracy value #4 exists to prevent" (export_sources.py).
//
// WHAT "SHIPS" MEANS, in one place: shipping() below. It is
// export_sources.build_output()'s rule on its default (dbt) path. Until the
// dbt cutover, production phones carry the 28 that the exporters' path
// counts (build_output(exporters_only=True)); the maintainer chose the dbt
// path's count knowing that (poll, 2026-10-23).

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

/** pipeline/sources.json, parsed. The site builds, and its tests run, from
 *  site/ in a checkout of the whole repository (pages.yml, pr-preview.yml,
 *  client-tests.yml), as data/quality/index.astro already relies on. No
 *  fallback: a page counting nobody is worse than a build that stops and
 *  says why. */
export function readRegistry(path = resolve(process.cwd(), "../pipeline/sources.json")) {
  return JSON.parse(readFileSync(path, "utf8"));
}

/** Every registered organization, A-Z, as `{ name, datasets }`.
 *
 *  `datasets` counts that organization's `reaches_hikers: true` sources -
 *  zero for one registered with nothing shipping. Sources join to
 *  organizations on `provider`, as export_sources.py and
 *  pipeline/tests/test_organizations.py do. A shipping source whose provider
 *  has no organization record is listed under its provider string - the same
 *  fallback export_sources.py's `name` takes - rather than dropped. */
export function registeredOrgs(registry) {
  const byProvider = new Map();
  for (const org of Object.values(registry?.organizations?.orgs ?? {})) {
    byProvider.set(org.provider, { name: org.name, datasets: 0 });
  }
  for (const source of registry?.sources ?? []) {
    if (source.reaches_hikers !== true) continue;
    if (!byProvider.has(source.provider)) byProvider.set(source.provider, { name: source.provider, datasets: 0 });
    byProvider.get(source.provider).datasets += 1;
  }
  return [...byProvider.values()].sort((a, b) => a.name.localeCompare(b.name, "en", { sensitivity: "base" }));
}

/** The organizations with data that ships: at least one dataset. */
export function shipping(roster) {
  return roster.filter((org) => org.datasets > 0);
}

/** The roster under its first letters, in order, for the page's index: each
 *  `{ letter, orgs }`. A name that does not start with A-Z goes under "#",
 *  last, so it is listed rather than lost; none does today. */
export function byFirstLetter(roster) {
  const groups = new Map();
  for (const org of roster) {
    const first = org.name.charAt(0).toUpperCase();
    const letter = first >= "A" && first <= "Z" ? first : "#";
    if (!groups.has(letter)) groups.set(letter, []);
    groups.get(letter).push(org);
  }
  return [...groups.keys()]
    .sort((a, b) => (a === "#") - (b === "#") || a.localeCompare(b))
    .map((letter) => ({ letter, orgs: groups.get(letter) }));
}
