"""Monadnock-Sunapee Greenway Trail Club: warnings, nothing published (coverage audit 2026-10-01, batch
p03_persist).

NHFG WMU: none_stated ("The data presented are for information purposes only…"). msgtc.org sets
`Crawl-delay: 10`. My robots request and two media requests went out within seconds of each other,
and I sent nothing further.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Neither the club nor its land managers publish a dated hazard notice as GIS or as a feed. Two things "
        "were found that are not warnings. NH Fish and Game's "
        "`services8.arcgis.com/hg1B9Egwk1I5p300/arcgis/rest/services/WMU/FeatureServer/0` (24 wildlife "
        "management unit polygons, edited 2026-08-26, with deer, moose, turkey and bear units in layers 1–7) "
        "carries no season dates. NH State Parks' "
        "`/find-parks-trails/find-a-trail/trail-advisories-and-closures` (HTTP 200) is OHRV trail status and "
        "has no entry for Pillsbury, Mount Sunapee or Monadnock. Tried: 1 GRANIT …",
    ),
    where=(
        "https://services8.arcgis.com/hg1B9Egwk1I5p300/arcgis/rest/services/WMU/FeatureServer/0",
        "https://msgtc.org",
        "https://msgtc.org/",
        "https://nhgeodata.unh.edu/nhgeodata/rest/services",
    ),
)
