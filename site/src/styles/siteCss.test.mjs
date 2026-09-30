// Contracts on site.css that a render would show and a unit test can still
// read: each one below is a bug that shipped on the /for-orgs/ pages and was
// only found by photographing them at 390px (#1663 - The /for-orgs/ pages are
// unreadable in dark mode and misaligned on a phone). None of them needs
// layout to detect, so none of them needs a browser to guard.

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const SITE = fileURLToPath(new URL("../..", import.meta.url));
const read = (path) => readFileSync(join(SITE, path), "utf8");

const css = read("src/styles/site.css");
const tokens = read("../client/src/design-system/tokens/colors.css");

function astroFiles(dir) {
  return readdirSync(join(SITE, dir)).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(join(SITE, path)).isDirectory()) return astroFiles(path);
    return path.endsWith(".astro") ? [path] : [];
  });
}

/** The body of the first block that opens with `head`, braces balanced. */
function block(source, head) {
  const at = source.indexOf(head);
  expect(at, `${head} not found`).toBeGreaterThan(-1);
  let depth = 0;
  for (let i = source.indexOf("{", at); i < source.length; i += 1) {
    if (source[i] === "{") depth += 1;
    if (source[i] === "}" && (depth -= 1) === 0) {
      return source.slice(source.indexOf("{", at) + 1, i);
    }
  }
  throw new Error(`${head} never closes`);
}

const declared = (body) =>
  new Set([...body.matchAll(/^\s*(--[\w-]+)\s*:/gm)].map((m) => m[1]));

describe("the dark-mode block", () => {
  // site.css mirrors the tokens' `[data-theme='dark']` block by hand, behind
  // the OS preference, because the site has no theme JS. It was "kept
  // deliberately short", and short left out the four surfaces the org
  // components sit on: text flipped to bone, the cards and fields under it
  // stayed paper, 1.21:1 (measured 2026-09-24).
  const siteDark = declared(block(css, "@media (prefers-color-scheme: dark)"));
  const tokensDark = declared(block(tokens, ":root[data-theme='dark']"));
  const read_ = new Set(
    [css, ...astroFiles("src").map(read)].flatMap((source) =>
      [...source.matchAll(/var\((--[\w-]+)/g)].map((m) => m[1]),
    ),
  );

  it("re-points every alias the site reads that the tokens' dark block re-points", () => {
    const missing = [...read_].filter(
      (alias) => tokensDark.has(alias) && !siteDark.has(alias),
    );
    expect(missing).toEqual([]);
  });

  it("points each alias it mirrors where the tokens' dark block points it", () => {
    // The first test catches an alias left out; this one catches an alias
    // left behind. #1670 - --fg-3 text is under WCAG AA contrast on every
    // light surface, and the app uses it 229 times - moved the dark `--fg-3`
    // and `--fg-chrome-3` from bone-500 to bone-400 in colors.css, and a
    // mirror that kept bone-500 would still have listed both names.
    const values = (body) =>
      new Map(
        [...body.matchAll(/^\s*(--[\w-]+)\s*:\s*([^;]+);/gm)].map((m) => [m[1], m[2].trim()]),
      );
    const site = values(block(css, "@media (prefers-color-scheme: dark)"));
    const theirs = values(block(tokens, ":root[data-theme='dark']"));
    const drifted = [...site]
      .filter(([alias, value]) => theirs.has(alias) && theirs.get(alias) !== value)
      .map(([alias, value]) => `${alias}: site ${value}, tokens ${theirs.get(alias)}`);
    expect(drifted).toEqual([]);
  });
});

describe("classes the org pages use", () => {
  // Nominate's website field carried `org-field__label` and
  // `org-field__input` from 53cfedc7 on, and no stylesheet has ever defined
  // either: the one input on the page rendered as a bare browser box.
  const defined = new Set([...css.matchAll(/\.([a-zA-Z][\w-]*)/g)].map((m) => m[1]));

  // Classes that are there for a script or for the markup's own sake and
  // are meant to carry no rule. Each is named with the reason, so adding one
  // is a decision rather than a way to quiet the test.
  const HOOKS = {
    "org-identity__in": "the signed-in half of the gate; the script toggles `hidden` on it",
    "org-steps": "a plain ordered list, deliberately left to the browser's numbering",
  };

  for (const page of astroFiles("src/pages/for-orgs")) {
    it(`${page} names no class the stylesheets do not define`, () => {
      const source = read(page);
      const scoped = new Set(
        [...source.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].flatMap((m) =>
          [...m[1].matchAll(/\.([a-zA-Z][\w-]*)/g)].map((c) => c[1]),
        ),
      );
      const used = [...source.matchAll(/class="([^"{]*)"/g)].flatMap((m) =>
        m[1].split(/\s+/).filter(Boolean),
      );
      const undefined_ = used.filter(
        (name) => !defined.has(name) && !scoped.has(name) && !(name in HOOKS),
      );
      expect(undefined_).toEqual([]);
    });
  }
});

describe("rules that share an element with .wrap", () => {
  // `.nav` is on `<nav class="wrap nav">` and set `padding: 18px 0`. It comes
  // after `.wrap` in this file, so the shorthand zeroed the 24px gutter on
  // every page: invisible on a desktop, the logo on the edge of a phone.
  const partners = new Set(
    astroFiles("src").flatMap((path) =>
      [...read(path).matchAll(/class="([^"{]*)"/g)]
        .map((m) => m[1].split(/\s+/))
        .filter((names) => names.includes("wrap"))
        .flatMap((names) => names.filter((name) => name !== "wrap")),
    ),
  );

  for (const name of partners) {
    it(`.${name} never uses the padding shorthand`, () => {
      const rules = [...css.matchAll(new RegExp(`\\.${name}\\s*\\{([^}]*)\\}`, "g"))];
      for (const [, body] of rules) {
        expect(body).not.toMatch(/(^|[\s;])padding\s*:/);
      }
    });
  }
});

describe("buttons", () => {
  // `.btn` was written for links and used on <button> too, which kept the
  // browser's own border - a dark bevel round "Read their site".
  it("resets the border a <button class=\"btn\"> brings with it", () => {
    expect(block(css, ".btn {")).toMatch(/\bborder:\s*0/);
  });
});

describe("the org hero", () => {
  // Both layers are positioned with no z-index between them, so document
  // order decides which is on top. The comment always said the contours
  // stay underneath the photograph; the markup put them second.
  it("draws the contours before the photograph, so the photograph covers them", () => {
    const page = read("src/pages/for-orgs/index.astro");
    const body = page.slice(page.indexOf('<header class="hero hero--org">'));
    expect(body.indexOf("<Contours />")).toBeGreaterThan(-1);
    expect(body.indexOf("<Contours />")).toBeLessThan(body.indexOf('class="hero__photo"'));
  });

  it("positions the ridge, or its z-index is ignored", () => {
    expect(block(css, ".hero--org .ridge {")).toMatch(/position:\s*relative/);
  });
});
