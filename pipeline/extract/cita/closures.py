"""Central Iowa Trail Association: closures, unreadable: the status app's robots.txt answers HTTP 500
(decision 53 phase B, 2026-10-03).

The status app (https://status.centraliowatrails.com/) is the best-structured open-or-closed source
the inventory found: 10 areas, each with a stable code (BAN, CEN, DEN, EWG, FOUR, FLOW, GRA, SYC,
and the non-CITA AQB and WRC), an open or closed badge and the days since its last update (batch 2,
2026-10-03). Its robots.txt answered HTTP 500 with an empty body to the inventory and again at
2026-10-03T22:00:39Z, and RFC 9309 §2.3.1.4 reads a 5xx robots.txt as complete disallow, so nothing
is fetched. That the app answers 500 to every unknown route (Reasoned: /api/v1/status/CITA did too)
suggests it has no robots route rather than a rule; what would settle it is a robots.txt that
answers 2xx or 4xx on a later day, or CITA's word. Its API's `updateByDisplay` and `trail.stewards`
are person fields (ELT.md rule 8) and never load, whichever way it is read. AQB's 'closed' was 466
days old when read, so a row's age travels with it if it ever lands.

Before decision 53 phase B, 2026-10-03, this note read:

Central Iowa Trail Association: closures, published, and not landed (coverage audit 2026-10-01,
batch c5_regional_2).

The only live, structured open/closed source in this batch. The days-since-update figure must travel
with each row, because a 463-day-old "closed" is not a current fact. (Skeptic, 2026-10-01: same
verdict, better format. JSON API `/api/v1/status/{CITA|CITA-OTHER}/{code}` gives …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `https://status.centraliowatrails.com/`, server-rendered HTML.
Each of 8 CITA areas plus 2 non-CITA areas has a `<div class="badge open|closed">CODE`, a condition
word, and days since the last update. Snapshot 2026-10-01 ~03:30 UTC: CITA open BAN, CEN, DEN;
closed EWG, FOUR, FLOW, GRA, SYC. Non-CITA AQB closed (463 d since update), WRC open (162 d).
`/fourmilemtb`: "freeze/thaw or heavy rains cause the trails to close".

Its `where`: https://status.centraliowatrails.com/ https://bikecita.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "(the decision 53 inventory, batch 2, 2026-10-03) https://status.centraliowatrails.com/: 200, 10 area badges (open BAN, CEN, DEN, WRC; closed EWG, FOUR, FLOW, GRA, SYC, AQB); https://status.centraliowatrails.com/robots.txt: HTTP 500, empty body (server Kestrel).",
        "https://status.centraliowatrails.com/robots.txt re-read at 2026-10-03T22:00:39Z under lib/user_agent.py's agent: HTTP 500 again, so the page was not requested.",
    ),
    where=(
        "https://status.centraliowatrails.com/",
        "https://status.centraliowatrails.com/robots.txt",
    ),
    reason="unreadable: robots.txt answers 5xx, which RFC 9309 reads as disallow; recheck it, or ask CITA",
    recheck_after_days=30,
)
