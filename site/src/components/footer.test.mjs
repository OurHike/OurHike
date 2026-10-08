// The site footer's links to the data pages: the dbt docs at /data/ and the
// data-quality page at /data/quality/, as the last two lines of "The project"
// on every page (the maintainer's choice, 2026-10-08; pipeline/ELT.md
// decision 102). Read from source, like treadCard.test.mjs, because what this
// guards against - the two lines dropped, reordered or pointed elsewhere - is
// a line of source; client/e2e/sitePages.spec.ts already holds every footer
// link to a phone-sized target in a browser.

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const SITE = fileURLToPath(new URL("../..", import.meta.url));
const read = (path) => readFileSync(join(SITE, path), "utf8");
const footer = read("src/components/Footer.astro");

/** [href, label] for each link in the footer column headed `heading`. */
function column(heading) {
  const start = footer.indexOf(`>${heading}</span>`);
  expect(start, `no footer column headed ${heading}`).toBeGreaterThan(-1);
  const body = footer.slice(start, footer.indexOf("</div>", start));
  return [...body.matchAll(/<a href="([^"]+)">([^<]+)<\/a>/g)].map((m) => [m[1], m[2].trim()]);
}

function pages(dir = "src/pages") {
  return readdirSync(join(SITE, dir)).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(join(SITE, path)).isDirectory()) return pages(path);
    return path.endsWith(".astro") ? [path] : [];
  });
}

describe("the footer's data links", () => {
  it('end "The project" with Data docs and then Data quality', () => {
    expect(column("THE PROJECT").slice(-2)).toEqual([
      ["/data/", "Data docs"],
      ["/data/quality/", "Data quality"],
    ]);
  });

  it("keep the column's other links ahead of them", () => {
    expect(column("THE PROJECT").slice(0, -2).map(([href]) => href)).toEqual([
      "https://github.com/OurHike/OurHike",
      "https://github.com/OurHike/OurHike/issues",
      "/app/",
    ]);
  });

  it("point at a data-quality page this site builds, and at a /data/ it leaves to the docs", () => {
    // /data/ itself is the dbt docs, which pages.yml and pr-preview.yml copy
    // in when they assemble the site, and which refuse a site that puts
    // anything but data/quality/ there.
    expect(existsSync(join(SITE, "src/pages/data/quality/index.astro"))).toBe(true);
    expect(existsSync(join(SITE, "src/pages/data/index.astro"))).toBe(false);
  });

  it("reach every page, because every page is drawn in the layout that renders the footer", () => {
    expect(read("src/layouts/Base.astro")).toContain("<Footer />");
    const outside = pages().filter((page) => !read(page).includes("<Base"));
    expect(outside).toEqual([]);
  });
});
