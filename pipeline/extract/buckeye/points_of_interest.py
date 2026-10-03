"""Buckeye Trail Association: points of interest, published, and held until the association permits.

BTA's parking layer is public on ArcGIS Online, and its item states nothing; but BTA's own trail-line item,
the same owner's, reads 'Permission from the Buckeye Trail Assocation is required before use!', and
buckeye is one of the four `refuse` rows in trail_orgs.json. Decision 39 counts a club's own public ArcGIS
layer as published, which is ONDA's case; whether it reaches a layer whose publisher asks for permission in
so many words is the maintainer's call, so this stays a note and the maintainer sends the ask.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "parking_web_final/FeatureServer/0, 422 points, GlobalID unique (422 of 422), fields Name, "
        "type_pking, term_pking and access_pki beside editor tracking, last edited 2020-09-19 (read "
        "2026-10-03); its item's licenseInfo is empty and accessInformation reads 'Buckeye Trail Association'",
        "BT_trail_line_updated/FeatureServer/0's item, read 2026-10-03: licenseInfo 'Permission from the "
        "Buckeye Trail Assocation is required before use!'",
    ),
    where=(
        "https://services.arcgis.com/VV0wGgcoagcH1JO8/arcgis/rest/services/parking_web_final/FeatureServer/0",
        "https://services.arcgis.com/VV0wGgcoagcH1JO8/arcgis/rest/services/BT_trail_line_updated/FeatureServer/0",
    ),
    reason=(
        "published, and held: the publisher asks for permission before use, and buckeye is a refuse row; the "
        "maintainer sends the ask"
    ),
    terms="Permission from the Buckeye Trail Assocation is required before use!",
)
