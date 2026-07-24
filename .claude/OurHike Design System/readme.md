# OurHike Design System

A design system for **OurHike** — inspired visually by the New York-New Jersey Trail Conference (nynjtc.org), a volunteer-powered nonprofit, founded 1920, that builds, maintains, and protects 2,100+ miles of public trails across the NY/NJ metro region.

**Company line given for this project:** "Blaze your path, hike your own hike & connect with the communities that maintain our trails."

## Sources
- Aesthetic reference: https://www.nynjtc.org/ (homepage, About Us, Membership, site-overview pages) — used only as a style/tone reference; all copy and branding here is written for OurHike.
- No Figma file, codebase, or brand asset package was attached or accessible this run — everything below was built from the reference site's **public page copy and mission content** read via web research, not from CSS/design-file inspection. **No OurHike logo file was available**, so a plain-type wordmark stands in everywhere a mark would go (see `guidelines/brand-wordmark.card.html`).
- If you have OurHike's actual brand guide, logo files, font files, or a Figma link, attach them and ask for a refresh — this system will be corrected against real source material.

## Content fundamentals
- **Voice:** warm, plain-spoken, mission-driven register, modeled on the trail-conference reference. Mix of "we" (organizational voice) and direct "you" address in calls to action.
- **Values-forward statements, short declaratives** — e.g. "The joys of nature belong to everyone... Volunteers are our superheroes. Creating and protecting trails is a labor of love... Environmental conservation is a shared duty."
- Casing: sentence case for body copy and headings (not Title Case). No emoji in on-site copy.
- Numbers used sparingly but concretely for credibility (e.g. "2,100+ miles of trail").
- Calls to action are direct and low-pressure: "Find a Trail," "Join Today," "Donate" — never hard-sell.

## Visual foundations
No direct CSS/asset access was possible this run, so the palette and system below is an **original interpretation** grounded in the reference brand's actual subject matter — hiking trails, painted trail blazes, forests — rather than a pixel-accurate trace:
- **Color:** deep pine/forest greens as the dominant brand color (canopy, conservation), warm stone/paper neutrals (trailhead signage, parchment maps), and a small trio of "blaze" accent colors — red, yellow, blue — deliberately named after the painted paint-blazes hikers follow on trail trees, used sparingly for CTAs and status tags only.
- **Type:** a sturdy slab serif (Bitter) for display/headlines — evokes carved trail signage — paired with a clean humanist sans (Public Sans) for body/UI, and a monospace (IBM Plex Mono) for coordinates/mile-markers/trail codes.
- **Spacing:** 4px base unit scale (4/8/16/24/32/48/64/80/96/128).
- **Corners & cards:** cards are white, gently rounded (8–14px), 1px hairline border + soft drop shadow — no colored left-border accent stripes.
- **Buttons:** full pill radius, forest-green primary, blaze-orange secondary (donate/urgent), subtle hover-darken and press-scale (no bounce).
- **Backgrounds:** full-bleed hero sections in dark pine gradient; content sections on warm paper/white; no gradients-as-decoration outside the hero.
- **Imagery:** intended to be full-color outdoor photography (trail, forest, ridge views) — warm/natural color grading, not B&W. No real photography was available, so placeholders (soft green/stone gradients) stand in — swap in real trail photography when available.
- **Motion:** minimal — fast (120–200ms) ease-standard fades/color transitions only; buttons scale to 97% on press. No bounce/spring easing.
- **Borders/shadows:** hairline 1px borders in stone-150; two shadow levels (card, raised) — no inner shadows except form-field focus rings (soft forest-green glow).

## Iconography
No icon font, SVG sprite, or icon system was found in accessible sources. Recommendation documented in `guidelines/imagery-iconography.card.html`: simple 1.5px-stroke line icons (e.g. Lucide, CDN-linked) for compass/map/mile-marker glyphs; no emoji in UI. **Flag:** if OurHike has an existing icon set, provide it and this section will be replaced with the real assets.

## Fonts — substitution flag
No webfont files were available. Substituted nearest Google Fonts matches: **Bitter** (display/slab), **Public Sans** (body/UI), **IBM Plex Mono** (mono/data). Loaded via Google Fonts CDN in `tokens/typography.css`. **Please share OurHike's actual brand fonts (if any) so these can be replaced with real files.**

## Index
- `styles.css` — root stylesheet, imports all tokens
- `tokens/` — `colors.css`, `typography.css`, `spacing.css`, `effects.css` (radius/shadow/motion)
- `guidelines/` — foundation specimen cards (Colors, Type, Spacing, Brand groups)
- `components/core/` — Button, Badge, Card
- `components/forms/` — Input, Select
- `components/navigation/` — NavBar, Footer
- `components/feedback/` — Callout
- `ui_kits/website/` — homepage recreation (`index.html`, `Homepage.jsx`)
- `SKILL.md` — portable skill file for use in Claude Code

## Intentional additions
No source component library was available, so a standard nonprofit-site component set was authored from scratch (Button, Badge, Card, Input, Select, NavBar, Footer, Callout) sized to what a trail-conservation site needs (trail listings, difficulty tags, membership CTAs, closures/alerts).

## Caveats — please help me iterate
1. **No design-file or codebase access this run** — only public reference-site page text was available, no real CSS, exact hex values, or type specs. Everything visual here is an informed, trail-themed original for OurHike, not a trace of any existing site.
2. **No OurHike logo or icon assets available** — a plain-type wordmark stands in; no icons were copied in.
3. **Fonts are Google Fonts substitutes**, not OurHike's real brand fonts.
4. **The website UI kit is one interpretive homepage**, not a full site audit.

**Bold ask:** if you can attach OurHike's Figma file, a link to its site repo, or its actual logo/font files, I can replace every placeholder above with the real thing and get this system pixel-accurate. Please share what you have!
