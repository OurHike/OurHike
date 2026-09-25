// The Tread card on /for-orgs/demo/ reads the app's demo volunteer, and names
// nobody itself (#1663 - The /for-orgs/ pages are unreadable in dark mode and
// misaligned on a phone).
//
// The maintainer chose this by poll on 2026-09-24: the button under the card
// opens the app's /my/tread, which renders client/src/org/demoVolunteer.ts,
// so a card typed out here would show one volunteer and the full view
// another. These read the source rather than a build because the failure
// they guard - somebody pasting "Sam, 1.2 miles" back in from the design
// handoff - is a line of source, and it is what a reviewer would miss.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { DEMO_VOLUNTEER } from "../../../client/src/org/demoVolunteer";

const read = (path) =>
  readFileSync(fileURLToPath(new URL(path, import.meta.url)), "utf8");

const card = read("./TreadCard.astro");
const demo = read("../pages/for-orgs/demo.astro");
const markup = (source) => source.slice(source.indexOf("\n---", 4) + 4);

describe("the demo's Tread card", () => {
  it("reads the volunteer from the app's demo fixture", () => {
    expect(card).toContain("from '../../../client/src/org/demoVolunteer'");
    expect(card).toContain("DEMO_VOLUNTEER.displayName");
  });

  it("types no volunteer, section length or count into its markup", () => {
    // The handoff's Sam and the fixture's Alex, the handoff's 1.2 miles and
    // the fixture's 3.3: none of them may appear as literal text, only as
    // what the fixture says.
    for (const literal of [
      "Sam",
      DEMO_VOLUNTEER.displayName,
      String(DEMO_VOLUNTEER.miles),
      "1.2 mi",
    ]) {
      expect(markup(card)).not.toContain(literal);
    }
  });

  it("is drawn under the demo page's heading that promises it", () => {
    const section = demo.slice(demo.indexOf("The view that matters most"));
    expect(section.indexOf("<TreadCard")).toBeGreaterThan(-1);
    expect(section.indexOf("<TreadCard")).toBeLessThan(section.indexOf("<section"));
  });

  it("names the fixture's volunteer in the prose, not the handoff's", () => {
    expect(markup(demo)).not.toMatch(/\bSam\b/);
    expect(demo).toContain("DEMO_VOLUNTEER.displayName");
  });
});
