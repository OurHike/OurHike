"""USDA Forest Service: challenges, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

No public list of check-in locations was found. The data lives in OuterSpatial, which decision 18
places in `_shared/`. A candidate for #1780 — Let a club publish a challenge — places on its own
trails that hikers opt into and tag at camp — starting with the ATC's A.T. Summer Bucket List only
if …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "National Forests and Grasslands Passport: "
        "`https://www.fs.usda.gov/inside-fs/leadership/introducing-national-forests-and-grasslands-passport`, "
        'dated 2026-08-27. Digital check-ins and badges for all "154 national forests and 20 national '
        'grasslands", "in partnership with the National Forest Foundation", inside the OuterSpatial app. Nez '
        "Perce NHT passport PDF (c11). Junior Forest Ranger (a children's booklet, not place-based).",
    ),
    where=("https://www.fs.usda.gov/inside-fs/leadership/introducing-national-forests-and-grasslands-passport",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
