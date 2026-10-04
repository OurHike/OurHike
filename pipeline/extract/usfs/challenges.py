"""U.S. Forest Service: challenges, the National Forests and Grasslands Passport, in an app, and not landed
(decision 54 wave 4, section K, 2026-10-04).

The Passport ('154 national forests and 20 national grasslands', with the National Forest Foundation) is digital
check-ins and badges inside the OuterSpatial app; an app's content is not a page this pipeline reads. The PATC
challenge's eligible-trail list the page cell names is an Airtable shared view, patc/challenges.py's. The Junior
Forest Ranger booklet is a children's activity book, not place-based. No request sent today.

The note this replaces read, whole:

USDA Forest Service: challenges, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

No public list of check-in locations was found. The data lives in OuterSpatial, which decision 18 places
in `_shared/`. A candidate for #1780 — Let a club publish a challenge — places on its own trails that
hikers opt into and tag at camp — starting with the ATC's A.T. Summer Bucket List only if …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): National Forests and Grasslands Passport:
`https://www.fs.usda.gov/inside-fs/leadership/introducing-national-forests-and-grasslands-passport`,
dated 2026-08-27. Digital check-ins and badges for all "154 national forests and 20 national
grasslands", "in partnership with the National Forest Foundation", inside the OuterSpatial app. Nez
Perce NHT passport PDF (c11). Junior Forest Ranger (a children's booklet, not place-based).

Its `where`:
https://www.fs.usda.gov/inside-fs/leadership/introducing-national-forests-and-grasslands-passport

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) the Passport announcement, 2026-08-27: check-ins and badges in the OuterSpatial app",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://www.fs.usda.gov/inside-fs/leadership/introducing-national-forests-and-grasslands-passport",),
    reason="not published as a page: the passport lives in an app",
)
