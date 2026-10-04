"""CT DEEP: challenges, the Sky's the Limit Challenge, in an app, and not landed (decision 54 wave 5, section
K, 2026-10-04).

The 2026 Sky's the Limit Hiking and Walking Challenge (16 April to 4 December 2026) runs its missions in the
Goosechase app ('Download the Goosechase app ... Enter the game code'); the page lists no locations itself.

The note this replaces read, whole:

Connecticut DEEP: challenges, published, and not landed (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

It fits #1780 — Let a club publish a challenge — places on its own trails that hikers opt into and tag
at camp — starting with the ATC's A.T. Summer Bucket List's model of a named list of places. But the
mission details and check-in points live inside Goosechase, not on the page, so only the 20 …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): "Sky's the Limit Hiking and Walking Challenge 2026",
`https://ctparks.com/skys-the-limit-hiking-challenge` (200, read 2026-10-01). Found via the retired
portal page `https://portal.ct.gov/deep/state-parks/skys-the-limit` (200; "this page is no longer
active… can be found on the Sky's the Limit Hiking webpage"). Theme "America's 250th". 20 designated
State Park and Forest locations, named on the page. The first five are Beckley Furnace Industrial
Monument, Bluff Point SP, CCC Museum at Shenipsit SF, Collis P. Huntington SP and Dennis Hill SP. The
list runs on through Sleeping Giant SP. …

Its `where`: https://ctparks.com/skys-the-limit-hiking-challenge
https://portal.ct.gov/deep/state-parks/skys-the-limit

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://ctparks.com/skys-the-limit-hiking-challenge (HTTP 200, 139,397 bytes, 2026-10-04): 'Using the Goosechase app, you'll complete fun, interactive missions'",
    ),
    where=("https://ctparks.com/skys-the-limit-hiking-challenge",),
    reason="not published as a page: the challenge's locations live in an app",
)
