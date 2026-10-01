"""Monadnock-Sunapee Greenway Trail Club: places, published, and not landed (coverage audit 2026-10-01,
batch p03_persist).

none_stated: licenseInfo "Not for legal use", accessInformation "GRANIT database". The data belongs
in the `nh-granit` folder as a places layer. Reasoned: this does not reverse #1711 — Ship only
hiking trails: remove NH GRANIT, and drop USFS motorized trails nationwide, which removed GRANIT's
trail …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`nhgeodata.unh.edu/nhgeodata/rest/services/EC/Conservation/MapServer/6`, "CL: Solid" (13,502 '
        "polygons): 33 lie within 10 m of the 24 segments in GRANIT `CSD/RecreationResources/MapServer/2` whose"
        " `TRAILSYSTE` is the Greenway. Those segments fall in the towns of Dublin, Goshen, Harrisville, "
        "Nelson, Newbury, Stoddard and Washington. The 33 include Pillsbury State Park, Mount Sunapee State "
        "Park, Monadnock Reservation, Andorra Forest, Leighton, Lovewell Mountain and Max Israel state forests,"
        ' and Pitcher Mountain Fire Tower. A hosted copy is item `ac1d1c9b…`, "New Hampshire '
        "Conservation/Public …",
    ),
    where=(
        "https://nhgeodata.unh.edu/nhgeodata/rest/services/CSD/RecreationResources/MapServer/2",
        "https://nhgeodata.unh.edu/nhgeodata/rest/services/EC/Conservation/MapServer/6",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
