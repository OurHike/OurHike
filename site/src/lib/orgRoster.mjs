// The organizations page and the homepage's count (#1877), derived from
// pipeline/sources.json when the site is built rather than typed in.
//
// heroOrgs.mjs's ORGS was the roster until 2026-10-23: five organizations,
// typed by hand on 2026-08-26, while the registry grew to 150. Nothing
// noticed, because nothing read the registry. This does, so the page and the
// count move when the registry does.
//
// WHICH ORGANIZATIONS: every one with at least one source marked
// `reaches_hikers: true` - 111 of the 150 on main at 072fc298. That is
// export_sources.py's build_output() rule on its default path (the dbt
// path), which is what the app's sources screen names there. The maintainer
// chose it by poll, 2026-10-23, over the 28 that production's exporters read
// today (build_output(exporters_only=True)) and over all 150 registered, with
// the gap stated in the question: until the dbt cutover, production phones
// carry 28 of these 111. An organization registered with nothing shipping is
// left out for the reason export_sources.py gives: a page naming a steward
// whose data does not ship is "the same category of quiet inaccuracy value #4
// exists to prevent".

/** Every organization with a shipping source, A-Z, as `{ name, datasets }`.
 *
 *  `registry` is pipeline/sources.json, parsed. Sources join to
 *  organizations on `provider`, as export_sources.py and
 *  pipeline/tests/test_organizations.py do. `datasets` counts that
 *  organization's `reaches_hikers: true` sources - the number the page prints
 *  after each name - and never the ones registered but not shipped.
 *
 *  A shipping source whose provider has no organization record is named by
 *  its provider string - the same fallback export_sources.py's `name` takes -
 *  rather than dropped, because dropping it would make the count quietly
 *  smaller than what ships. */
export function orgsReachingHikers(registry) {
  const orgs = Object.values(registry?.organizations?.orgs ?? {});
  const nameByProvider = new Map(orgs.map((org) => [org.provider, org.name]));
  const byProvider = new Map();
  for (const source of registry?.sources ?? []) {
    if (source.reaches_hikers !== true) continue;
    const entry = byProvider.get(source.provider) ?? {
      name: nameByProvider.get(source.provider) ?? source.provider,
      datasets: 0,
    };
    entry.datasets += 1;
    byProvider.set(source.provider, entry);
  }
  return [...byProvider.values()].sort((a, b) =>
    a.name.localeCompare(b.name, "en", { sensitivity: "base" }),
  );
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
