"""Benton MacKaye Trail Association: challenges, a completion award with no list of places, and not landed (decision 54
wave 5, section K, 2026-10-04).

End-to-end recognition through a 'Completion Report & Request for Listing', and patches and rockers (thru-hike,
300, 500 and 1,000 miles) sold in its store.

The challenges type holds a club's list of places on its trails (pipeline/ELT.md, decision 3, what #1780 — Let a
club publish a challenge — places on its own trails that hikers opt into and tag at camp — starting with the ATC's
A.T. Summer Bucket List builds), and a finisher's roster is never loaded (the round brief).

The note this replaces read, whole:

Benton MacKaye Trail Association: challenges, published, and not landed (coverage audit 2026-10-01,
batch c8_regional_5).

The finisher table is people's names. Ingest the programme, never the list.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): End-to-end recognition through a "Completion Report & Request for
Listing" (`/thru-hikers-guide/#milers`). The BMTA sends one patch plus a Thru-Hike, 300-, 500- or
1,000-Mile rocker (`/product/trail-patch/`). Skeptic: `product-sitemap.xml` lists `trail-patch/`,
`thru-hiker-crescent/`, `300-miler-rocker/`, `500-miler-crescent/` and `1000-miler-crescent/`. So 300 is
a rocker, and thru-hike, 500 and 1,000 are crescents. The `100-hour-club` and `50-miler-hike-leader`
award forms in the page sitemap are volunteer awards, not hiker challenges.

Its `where`: https://bmta.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) /thru-hikers-guide/#milers and the store's product sitemap",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://bmta.org/thru-hikers-guide/",),
    reason="not this type: a completion award, with no list of places (ELT.md decision 3); its roster is never read",
)
