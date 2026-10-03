"""AMC Delaware Valley Chapter: closures, drawn from another folder's resource (coverage audit
2026-10-01, batch p02_persist).

Licence: NPS alerts: a federal work (Reasoned). PGC: attribution_only: "The PGC should be clearly
cited in any product derived from this Data. Any modifications to this Data must be described in any
digital or hardcopy product derived therefrom." Plus a hold-harmless clause. Folder: `atc` (loaded)
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Already LOADED: `atc_trail_updates`, 3 PA rows (audit). NPS alerts API `parkCode=appa,dewa`: 5 alerts."
        ' DEWA has "Dingmans Falls Trail, Road, and Access Closed for Bridge Replacement", "Old Mine Road North'
        ' Construction Closure", "Main Street Walpack Bridge Closed". APPA has the "List of trail closures '
        "post-Hurricane Helene\" and McAfee Knob bears. None is on AMC-DV's sections today. PA Game Commission: "
        "a spatial query of `https://pgcmaps.pa.gov/arcgis/rest/services/PGC/NEW_PUBLIC/MapServer/17` puts SGL "
        "168 under the Wind Gap–Little Gap section. `PGC/Seasonal_Roads/MapServer/0` has 34 segments …",
    ),
    where=(
        "https://pgcmaps.pa.gov/arcgis/rest/services/PGC/NEW_PUBLIC/MapServer/17",
        "https://pgcmaps.pa.gov/arcgis/rest/services/PGC/Seasonal_Roads/MapServer/0",
        "https://amcdv.org/feed/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
