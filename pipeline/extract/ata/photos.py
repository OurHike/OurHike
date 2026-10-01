"""Arizona Trail Association: photos, nothing published (coverage audit 2026-10-01, batch
c10_nst_rest).

No open licence.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Flickr "Arizona Trail Association" (`79177693@N02`): the first 25 photos are all `license: 0` (All '
        "rights reserved). The ArcGIS `ATA_StoryMap_PhotoPoints` (174) points at those same Flickr images.",
    ),
    where=(
        "https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services",
        "https://aztrail.org/",
    ),
)
