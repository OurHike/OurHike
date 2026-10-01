"""AMC Connecticut Chapter: places, published, and not landed (coverage audit 2026-10-01, batch
p01_persist).

Licence: open_licence, CC0 on both DEEP items (`licenseInfo` "CC0"; data.gov
`https://creativecommons.org/publicdomain/zero/1.0`). A state work, not federal. Folder: `ct-deep/`
(catalogue `ct-deep`, state_agency). The access-point layer is also a POI and trailhead source for
`ct-deep/`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'CT DEEP (org `FjPcSmEFuDYlIdKC`, "Department of Energy & Environmental Protection", 504 services):',
        "`Connecticut_DEEP_Property/FeatureServer/0` (item `ce4e1d18…`, owner `deepgis`): 491 polygons, last "
        "edit 2026-08-19. Along CT's A.T. it holds Housatonic State Forest, Housatonic Meadows SP, Kent Falls "
        "SP, Macedonia Brook SP (the audit's bridge closure), Mohawk SF and Mount Riga State Park Scenic "
        "Reserve.",
        "`DEEP_Property_Access_Locations/FeatureServer/0` (item `3df3c20f…`): 385 access points, last edit "
        "2026-04-21, with `HIKING`, `CAMPING`, `CAMP_BCKPK`, `OVRLK_TOWR`, `WATERFALL`, `STATUS`. …",
    ),
    where=(
        "https://creativecommons.org/publicdomain/zero/1.0",
        "https://services1.arcgis.com/FjPcSmEFuDYlIdKC/arcgis/rest/services/Connecticut_DEEP_Property/FeatureServer/0",
        "https://services1.arcgis.com/FjPcSmEFuDYlIdKC/arcgis/rest/services/DEEP_Property_Access_Locations/FeatureServer/0",
        "https://data.gov",
        "https://ct-amc.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
