"""Maah Daah Hey Trail Association: challenges, a completion award with no list of places, and not landed (decision 54
wave 5, section K, 2026-10-04).

The 2026 MDH Trail Challenge: miles 'earned from using any of the trails in the Maah Daah Hey Trail System',
self-reported on a mileage log, a patch at 25, 50, 100 or 150.

The challenges type holds a club's list of places on its trails (pipeline/ELT.md, decision 3, what #1780 — Let a
club publish a challenge — places on its own trails that hikers opt into and tag at camp — starting with the ATC's
A.T. Summer Bucket List builds), and a finisher's roster is never loaded (the round brief).

The note this replaces read, whole:

Maah Daah Hey Trail Association: challenges, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

Page. A tiered mileage challenge, not a place list.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): "2026 MDH Trail Challenge",
`https://mdhta.com/2024-mdh-trail-challenge/`: "Challenge miles can be earned from using any of the
trails in the Maah Daah Hey Trail System", self-reported on a downloadable mileage log. Skeptic,
re-read: "a patch for 25, 50, 100 or 150 will be awarded … For those completing 100 or 150 miles a
sticker and patch". The site sometimes sends `content-encoding: gzip` to a request with no
`Accept-Encoding`. I saw it on 3 requests, while an earlier `/trail-guide/` fetch came back plain. So a
loader must always decompress.

Its `where`: https://mdhta.com/2024-mdh-trail-challenge/ https://mdhta.com/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) /2024-mdh-trail-challenge/",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://mdhta.com/2024-mdh-trail-challenge/",),
    reason="not this type: a completion award, with no list of places (ELT.md decision 3); its roster is never read",
)
