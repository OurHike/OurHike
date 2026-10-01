"""Palmetto Conservation Foundation: trail lines, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

HTML-embedded, so it means scraping 33 pages. The MMPK is a 313 MB binary, not a service. Partly
LOADED via `usfs_trails` (about 92.3 mi, correction 7). `kblazzard_WCUEDU` layers (e.g. 108 feature
points) belong to a university person, so they are leads only.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "33 passage pages, `https://www.palmettotrail.org/trails/trail/<passage>` (`sitemap.xml`). Each embeds "
        "its line as inline JSON: `trailPage.helper.addSegment('EastatoePassage09282018', "
        '[{"lng":…,"lat":…},…])`. Also free per-passage Avenza maps, and the org\'s own ArcGIS account '
        '`palmettoconservation`, which holds a Mobile Map Package "Palmetto Trail - Statewide Map" (313,124,546'
        " B, modified 2026-08-25).",
    ),
    where=("https://www.palmettotrail.org/trails/trail/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
