import { describe, expect, it } from "vitest";
import { ORGS, allSlides, orgCountLine, rotationOrgs } from "./heroOrgs.mjs";
import { readRegistry, registeredOrgs } from "./orgRoster.mjs";

// A stand-in roster: the count line reads only its length, and rotationOrgs
// only its names. orgRoster.test.mjs holds the real registry.
const roster = (n) => Array.from({ length: n }, (_, i) => ({ name: `Organization ${i + 1}`, datasets: 1 }));
const everyOrg = ORGS.map((org) => ({ name: org.name, datasets: 1 }));

describe("the count line", () => {
  it("counts the roster it is given, not the hand-written ORGS", () => {
    expect(orgCountLine(roster(111))).toBe("Trail data from 111 organizations, offline.");
  });

  it("counts only the organizations with data that ships", () => {
    const registeredOnly = [...roster(111), { name: "Registered, nothing shipping", datasets: 0 }];
    expect(orgCountLine(registeredOnly)).toBe("Trail data from 111 organizations, offline.");
  });

  it("says organization, singular, for a roster of one", () => {
    expect(orgCountLine(roster(1))).toBe("Trail data from 1 organization, offline.");
  });

  it("grows when the roster does, without anybody editing the line", () => {
    // #1059 and #1877 were both this: a number typed in once that stayed put
    // while the roster grew (one organization to five, then five to 111).
    expect(orgCountLine(roster(112))).toBe(orgCountLine(roster(111)).replace("111", "112"));
  });
});

describe("the rotation", () => {
  it("opens on the count line", () => {
    expect(allSlides(everyOrg)[0]).toBe(orgCountLine(everyOrg));
  });

  it("carries every line of every organization on the roster", () => {
    const slides = allSlides(everyOrg);
    expect(slides).toEqual([orgCountLine(everyOrg), ...ORGS.flatMap((org) => org.lines)]);
  });

  it("drops the lines of an organization that is not on the roster", () => {
    const withoutAtc = everyOrg.filter((org) => org.name !== "Appalachian Trail Conservancy");
    const slides = allSlides(withoutAtc);
    expect(slides).not.toContain("The whole Appalachian Trail, offline.");
    expect(slides).toContain("The Tahoe Rim Trail, all the way around the lake.");
  });

  it("drops the lines of an organization that is registered but ships nothing", () => {
    const atcShipsNothing = everyOrg.map((org) =>
      org.name === "Appalachian Trail Conservancy" ? { ...org, datasets: 0 } : org,
    );
    expect(allSlides(atcShipsNothing)).not.toContain("The whole Appalachian Trail, offline.");
  });

  it("has no line repeated across organizations", () => {
    const lines = ORGS.flatMap((org) => org.lines);
    expect(new Set(lines).size).toBe(lines.length);
  });

  it("names each organization once", () => {
    const names = ORGS.map((org) => org.name);
    expect(new Set(names).size).toBe(names.length);
  });

  it("gives every organization a real lat/lon and at least one line", () => {
    for (const org of ORGS) {
      expect(org.lines.length).toBeGreaterThan(0);
      expect(Number.isFinite(org.lat)).toBe(true);
      expect(Number.isFinite(org.lon)).toBe(true);
    }
  });

  it("keeps every line within 84 characters, the longest of the five lines it started with", () => {
    // The headline is 56px Bitter: an 84-character line already takes four
    // lines on a 390px phone, and the hero grows with every line past that.
    const long = ORGS.flatMap((org) => org.lines).filter((line) => line.length > 84);
    expect(long).toEqual([]);
  });
});

describe("pipeline/sources.json as committed", () => {
  const real = registeredOrgs(readRegistry());

  it("has data that ships for every organization the rotation names, so no line is dropped", () => {
    const shipping = new Set(real.filter((org) => org.datasets > 0).map((org) => org.name));
    expect(ORGS.map((org) => org.name).filter((name) => !shipping.has(name))).toEqual([]);
    expect(rotationOrgs(real)).toEqual(ORGS);
  });
});
