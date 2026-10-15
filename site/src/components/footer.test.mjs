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

/** Every `<a href>` in `source` as [href, label], the href as the source writes it: `"…"` or `{`…`}`. */
function links(source) {
  return [...source.matchAll(/<a href=(?:"([^"]+)"|\{`([^`]+)`\})>([^<]+)<\/a>/g)].map((m) => [m[1] ?? m[2], m[3].trim()]);
}

/** [href, label] for each link in the footer column headed `heading`. */
function column(heading) {
  const start = footer.indexOf(`>${heading}</span>`);
  expect(start, `no footer column headed ${heading}`).toBeGreaterThan(-1);
  return links(footer.slice(start, footer.indexOf("</div>", start)));
}

function pages(dir = "src/pages") {
  return readdirSync(join(SITE, dir)).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(join(SITE, path)).isDirectory()) return pages(path);
    return path.endsWith(".astro") ? [path] : [];
  });
}

describe("the footer's data links", () => {
  it('end "The project" with How the data is built and then Data quality', () => {
    expect(column("THE PROJECT").slice(-2)).toEqual([
      ["${docs}/data/how/", "How the data is built"],
      ["${docs}/data/quality/", "Data quality"],
    ]);
  });

  it("keep the column's other links ahead of them", () => {
    expect(column("THE PROJECT").slice(0, -2).map(([href]) => href)).toEqual([
      "https://github.com/OurHike/OurHike",
      "https://github.com/OurHike/OurHike/issues",
      "${site}/app/",
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
    expect(read("src/layouts/Base.astro")).toContain("<Footer site={site} docs={docs} />");
    const outside = pages().filter((page) => !read(page).includes("<Base"));
    expect(outside).toEqual([]);
  });
});

// pipeline/ELT.md decision 144: the pages under /data/ are served from
// docs.ourhike.org too, a host with none of the site's other pages, and the
// site's data links point there once pages.yml finds it serving them. What
// each build writes was measured on 2026-10-10 by building the site both ways:
// with PUBLIC_DOCS_ORIGIN unset every page but data/quality/ came out
// byte-identical to the build before this change, and with it set only the
// footer's two data links moved. These hold the source to that.
describe("the site's links on two hosts", () => {
  it("name every one of the site's pages through `site`, so a page on the docs host names the site in full", () => {
    for (const path of ["src/components/Footer.astro", "src/components/NavBar.astro"]) {
      // Every href the source writes, quoted or as an expression.
      const hrefs = [...read(path).matchAll(/href=(?:"([^"]*)"|\{`([^`]*)`\}|\{([^}]*)\})/g)].map((m) => m[1] ?? m[2] ?? m[3]);
      const own = hrefs.filter((href) => !href.startsWith("https://") && !href.startsWith("${docs}"));
      expect(own.length, `${path} links to none of the site's pages`).toBeGreaterThan(0);
      for (const href of own) expect(href, `${path}`).toMatch(/^\$\{site\}/);
    }
    expect(read("src/components/NavBar.astro")).toContain("href={`${site}${link.href}`}");
  });

  it("work both prefixes out in the layout, from the page's path and the docs host pages.yml found", () => {
    const base = read("src/layouts/Base.astro");
    expect(base).toContain("Astro.url.pathname.startsWith('/data/')");
    expect(base).toContain("import.meta.env.PUBLIC_DOCS_ORIGIN");
    expect(base).toContain("<NavBar site={site} />");
  });

  it("keep the data pages' own tabs root-relative, because every host serving them serves /data/", () => {
    const nav = read("src/components/DataNav.astro");
    expect(nav).toContain("{ href: '/data/how/', label: 'How the data is built' }");
    expect(nav).toContain("{ href: '/data/quality/', label: 'Data quality' }");
  });
});
