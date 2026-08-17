# OurHike Design System (copied, owned here)

Copied from a `.claude/OurHike Design System/` directory on 2026-07-28 (a working
directory outside this repository - the rationale that mattered was carried into
[features/MAP_STYLE_SPEC.md](../../../features/MAP_STYLE_SPEC.md) and this copy).
This is a one-time copy, not a live sync: per the source's own guidance, "if
working on production code, you can copy assets... to become an expert in
designing with this brand."

**Not copied:** `components/navigation/{NavBar,Footer}` — marketing-site chrome
(Trails/Get Involved/Shop/About links, a Donate button), a different surface from
this app. The app's own bottom tab bar (Trail/More, see
[WIREFRAMES.md](../../../WIREFRAMES.md)) is built fresh in `src/chrome/`.

Import components via the barrel: `import { Button, Card } from './design-system/components'`.
