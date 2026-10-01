"""Waldo County Trails Coalition: places, published, and not landed (coverage audit 2026-10-01, batch
p08_persist).

Licence, Conserved Lands: "The ownership lines do not represent legal boundaries nor are the
ownership lines a survey. Conserved Lands is an inventory of approximate property boundaries. Access
to these lands is not implied. Permissions should always be granted by the landowner." Class:
none_stated …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "MEGIS `services1.arcgis.com/RbMX0mRVOFNTdLzd/.../Maine_Conserved_Lands_All/FeatureServer/0` (item "
        "`ad59f27a…`, modified 2026-07-01), in the trail's box (-69.40, 44.38, -68.98, 44.66; Unity to "
        'Belfast): 202 polygons. `PUB_ACCESS` breaks down as: "Contact landowner for additional information" '
        '112; "Allowed for general use(s)…" in 4 variants, 47; "Restricted - land owner permission required" '
        '19; "No public access" 9; "Restricted to trail area only" 2; "…Do not promote/publish without '
        'permission" 3; null 10. Public-access holders include Coastal Mountains Land Trust (Head of Tide, '
        "Piper Stream …",
    ),
    where=(
        "https://www.hillstosea.org/maps",
        "https://www.hillstosea.org/closures",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
