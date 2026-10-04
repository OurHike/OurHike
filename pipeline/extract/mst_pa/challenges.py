"""Mid State Trail Association: challenges, a completion award with no list of places, and not landed (decision 54 wave
5, section K, 2026-10-04).

/the-trail/end-to-end-list (certified end-to-enders since 2012, a roster), /resources/end-2-end-certification,
/resources/mega-meter and /the-organization/patches.

The challenges type holds a club's list of places on its trails (pipeline/ELT.md, decision 3, what #1780 — Let a
club publish a challenge — places on its own trails that hikers opt into and tag at camp — starting with the ATC's
A.T. Summer Bucket List builds), and a finisher's roster is never loaded (the round brief).

The note this replaces read, whole:

Mid State Trail Association (PA): challenges, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

Pages.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/the-trail/end-to-end-list` (certified end-to-enders since 2012),
`/resources/end-2-end-certification`, `/resources/mega-meter`, `/the-organization/patches`.

Its `where`: https://hike-mst.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) /index.php/the-trail/end-to-end-list",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://hike-mst.org/index.php/resources/end-2-end-certification",),
    reason="not this type: a completion award, with no list of places (ELT.md decision 3); its roster is never read",
)
