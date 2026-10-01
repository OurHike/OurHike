"""Wasatch Mountain Club: closures, published, and not landed (coverage audit 2026-10-01, batch
p08_persist).

Licence: USFS is open_licence, federal. Folder: `usfs/closures.py`. The R04 layer serves every R04
club, not just WMC. See Safety finds: the loaded SGID layer still marks the closed Big Cottonwood
trails `EXISTING`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "R04 order polygons: `fsgisx02/.../r04/R04_Alerts_And_Closures_01/MapServer/0`, `forestname LIKE "
        "'Uinta%'`: 96 polygons (Safety Closure 52, Closure for Resource Protection 29, Recreation Restriction "
        "9, Motor Vehicle Use Prohibition 4, Firearm Restriction 2). 22 Safety Closures started after "
        '2025-01-01 and end after today. Current ones in WMC\'s canyons: "Big Cottonwood Trail Closures" '
        '(04-19-26-744, 2026-08-20 → 2026-11-30): "Being in or upon the Mineral Fork Trail, Donut Falls '
        "Connector Trail, Jordan Pines Connector Trail, Mill D North Fork Trail, and Days Fork Trail. This "
        "includes all …",
    ),
    where=(
        "https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services",
        "https://wasatchmountainclub.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
