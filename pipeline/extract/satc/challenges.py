"""Susquehanna Appalachian Trail Club: challenges, nothing published (coverage audit 2026-10-01, batch
c2_at_clubs_mid).

The "State Forest Trails Award" this site mentions belongs to KTA/DCNR, so it goes in the kta folder
(batch c1).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/65-point-challenge-form.html` (in the sitemap, not the nav): a members' activity-points contest for "
        "SATC's 65th anniversary that closed 2020-03-01. `/giant-boot-award.html` is a volunteer-service award."
        ' "AT Hike Across PA #1–#25" on `/photos.html` is a series of club outings',
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://satc-hike.org/",
    ),
)
