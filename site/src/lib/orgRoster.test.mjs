import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { byFirstLetter, readRegistry, registeredOrgs, shipping } from "./orgRoster.mjs";

const registry = (orgs, sources) => ({ organizations: { orgs }, sources });

describe("registeredOrgs", () => {
  it("names an organization once, counting each of its shipping sources", () => {
    const roster = registeredOrgs(
      registry({ "org:atc": { provider: "ATC", name: "Appalachian Trail Conservancy" } }, [
        { key: "centerline", provider: "ATC", reaches_hikers: true },
        { key: "shelters", provider: "ATC", reaches_hikers: true },
      ]),
    );
    expect(roster).toEqual([{ name: "Appalachian Trail Conservancy", datasets: 2 }]);
  });

  it("lists an organization whose sources are all reaches_hikers: false, with no datasets", () => {
    const roster = registeredOrgs(
      registry(
        {
          "org:atc": { provider: "ATC", name: "Appalachian Trail Conservancy" },
          "org:gatc": { provider: "GATC", name: "Georgia Appalachian Trail Club" },
        },
        [
          { key: "centerline", provider: "ATC", reaches_hikers: true },
          { key: "gatc_water_sources", provider: "GATC", reaches_hikers: false },
        ],
      ),
    );
    expect(roster).toEqual([
      { name: "Appalachian Trail Conservancy", datasets: 1 },
      { name: "Georgia Appalachian Trail Club", datasets: 0 },
    ]);
    expect(shipping(roster).map((org) => org.name)).toEqual(["Appalachian Trail Conservancy"]);
  });

  it("counts only the shipping sources of an organization that also has some that do not ship", () => {
    const roster = registeredOrgs(
      registry({ "org:dec": { provider: "NYS DEC", name: "New York State Department of Environmental Conservation" } }, [
        { key: "dec_review", provider: "NYS DEC", reaches_hikers: false },
        { key: "dec_hiking_trails", provider: "NYS DEC", reaches_hikers: true },
      ]),
    );
    expect(roster).toEqual([{ name: "New York State Department of Environmental Conservation", datasets: 1 }]);
  });

  it("names a shipping source with no organization record by its provider, rather than dropping it", () => {
    const roster = registeredOrgs(registry({}, [{ key: "x", provider: "Unrecorded Trail Club", reaches_hikers: true }]));
    expect(roster).toEqual([{ name: "Unrecorded Trail Club", datasets: 1 }]);
  });

  it("sorts A-Z without letting an acronym's capitals jump the queue", () => {
    const roster = registeredOrgs(
      registry(
        {
          "org:b": { provider: "b", name: "Bay Area Ridge Trail Council" },
          "org:a": { provider: "a", name: "AMC" },
          "org:c": { provider: "c", name: "Alaska Trails" },
        },
        [
          { key: "1", provider: "b", reaches_hikers: true },
          { key: "2", provider: "a", reaches_hikers: true },
          { key: "3", provider: "c", reaches_hikers: true },
        ],
      ),
    );
    expect(roster.map((org) => org.name)).toEqual(["Alaska Trails", "AMC", "Bay Area Ridge Trail Council"]);
  });

  it("returns nothing for a registry it cannot read", () => {
    expect(registeredOrgs(undefined)).toEqual([]);
    expect(registeredOrgs({})).toEqual([]);
  });
});

describe("byFirstLetter", () => {
  const org = (name) => ({ name, datasets: 1 });

  it("groups the roster under its first letters, in alphabetical order", () => {
    const groups = byFirstLetter([org("Alaska Trails"), org("AMC"), org("Black Hills Trails")]);
    expect(groups.map((group) => group.letter)).toEqual(["A", "B"]);
    expect(groups[0].orgs.map((o) => o.name)).toEqual(["Alaska Trails", "AMC"]);
  });

  it("puts a name that does not start with a letter under #, after Z", () => {
    const groups = byFirstLetter([org("4 Peaks Trail Club"), org("Zion Forever")]);
    expect(groups.map((group) => group.letter)).toEqual(["Z", "#"]);
  });

  it("files a lower-case first letter under its capital", () => {
    expect(byFirstLetter([org("eTrails")])[0].letter).toBe("E");
  });
});

describe("pipeline/sources.json as committed", () => {
  const sources = readRegistry();
  const roster = registeredOrgs(sources);
  const shipped = sources.sources.filter((s) => s.reaches_hikers === true);

  it("lists every registered organization", () => {
    expect(roster.length).toBe(Object.keys(sources.organizations.orgs).length);
  });

  it("counts as shipping exactly the providers with a reaches_hikers: true source", () => {
    expect(shipping(roster).length).toBe(new Set(shipped.map((s) => s.provider)).size);
  });

  it("counts every shipping source exactly once across the roster", () => {
    expect(roster.reduce((sum, org) => sum + org.datasets, 0)).toBe(shipped.length);
  });

  it("names each organization by its registered name rather than its provider key", () => {
    const registered = new Set(Object.values(sources.organizations.orgs).map((org) => org.name));
    expect(roster.map((org) => org.name).filter((name) => !registered.has(name))).toEqual([]);
  });

  it("files every organization under a letter, none under #", () => {
    expect(byFirstLetter(roster).map((group) => group.letter)).not.toContain("#");
  });
});

describe("the site's pages", () => {
  // #1059 and #1877 were both a count typed into a page once - "one
  // organization", then "five organizations" on the homepage and on /about/ -
  // that stayed put while the registry grew. A page states a count through
  // registeredOrgs() and shipping(), never as a number in its copy. Comments
  // are stripped first, because several record what the copy used to say.
  const PAGES = join(import.meta.dirname, "../pages");
  const astro = (dir) =>
    readdirSync(dir).flatMap((name) => {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) return astro(path);
      return path.endsWith(".astro") ? [path] : [];
    });
  const copy = (source) =>
    source
      .replace(/<!--[\s\S]*?-->/g, "")
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/^\s*\/\/.*$/gm, "");
  const typedCount =
    /\b(?:one|two|three|four|five|six|seven|eight|nine|ten|\d[\d,]*)\s+(?:trail\s+)?(?:organi[sz]ations|stewards)\b/gi;

  it("type no organization count by hand", () => {
    const typed = astro(PAGES).flatMap((path) =>
      [...copy(readFileSync(path, "utf8")).matchAll(typedCount)].map((m) => `${path.slice(PAGES.length + 1)}: "${m[0]}"`),
    );
    expect(typed).toEqual([]);
  });
});
