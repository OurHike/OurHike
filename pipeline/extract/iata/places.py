"""Ice Age Trail Alliance: places, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

Skeptic spot-check: `Ice_Age_Trail_Communities_View/0` = 29, last edit 2026-07-30.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`.../Ice_Age_Trail_Communities_View/FeatureServer/0`: 29 trail communities, each with an itinerary "
        "link and community, tourism and chamber URLs. `.../IATA_Fee/FeatureServer/0`: 44 IATA property "
        "polygons with `Public_Access`. `.../Land_Ownership_Hosted_Public`: 194 polygons, last edit 2020-08-13.",
    ),
    where=(
        "https://dnrmaps.wi.gov/arcgis/rest/services",
        "https://iceagetrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
