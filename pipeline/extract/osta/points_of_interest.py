"""Old Spanish Trail Association: points of interest, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

One "Dispersed Camping" row falls under the existing `usfs_dispersed_camping_holdback` reasoning

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`OSNHT_MM_Framework`: trailheads 86, trail elements 86, POIs 196, information centers 28, certified "
        "sites 17, campgrounds 20 (Campground 4, Established 2, Dispersed Camping 1, 13 untyped), pack-mule "
        "silhouettes 27. Also NTIR POIs `olsp` 82 and `NPSAGOL/OLSP_High_Potential_Sites_Public` 54",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://oldspanishtrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
