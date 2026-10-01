"""Carolina Mountain Club: closures, published, and not landed (coverage audit 2026-10-01, batch
p01_persist).

Licence: EDW is public domain (federal work; maintainer's `usfs_licence`, 2026-09-02). The alerts
page is web prose, not GIS, and a federal work (Reasoned). Folder: `usfs/` (both); `nc-dpr/`;
`nps/`. Not CMC's. `openstatus` carries no date. @unvalidated: how soon it follows an order;
comparing it …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "USFS EDW `https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0`,"
        " `openstatus`, counted in rough boxes around CMC's sections:",
        "A.T. Davenport Gap–Spivey Gap (-83.12,35.75 to -82.30,36.12): 35 sites. open 5, closed 10, temporarily"
        " closed 1, none 19. Closed include Harmon Den Horsecamp, Rocky Bluff Campground, Murray Branch Picnic "
        "Area and Paint Creek Campground.",
        "Art Loeb / Pisgah RD (-82.95,35.22 to -82.68,35.45): 25 sites. open 23; Sliding Rock closed; Black "
        "Mountain / South Toe River Area temporarily closed.",
        "MST Waterrock Knob–Black Mountains …",
    ),
    where=("https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
