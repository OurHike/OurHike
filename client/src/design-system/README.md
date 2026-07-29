# OurHike Design System (copied, owned here)

Copied from `.claude/OurHike Design System/` on 2026-07-28 — see that directory's
own `readme.md`/`SKILL.md` for the full design rationale. This is a one-time copy,
not a live sync: per the source's own `SKILL.md`, "if working on production code,
you can copy assets... to become an expert in designing with this brand."

**Not copied:** `components/navigation/{NavBar,Footer}` — marketing-site chrome
(Trails/Get Involved/Shop/About links, a Donate button), a different surface from
this app. The app's own bottom tab bar (Trail/Downloads/More, see
[WIREFRAMES.md](../../../../WIREFRAMES.md)) is built fresh in `src/components/chrome/`.

Import components via the barrel: `import { Button, Card } from './design-system/components'`.
