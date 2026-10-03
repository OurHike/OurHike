"""Arizona Trail Association: points of interest, published, and not landed (coverage audit 2026-10-01,
batch c10_nst_rest).

The water `Type` needs a person-read mapping, like NPS's six spellings of potable water (c9). ATA
points hikers to FarOut's water report for current flow. FarOut is a third party, and its report is
not ATA's.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Layer `/0` AZT Water Source Locations: 312, last edit 2026-09-04 (skeptic: the layer's own "
        "`editingInfo.lastEditDate` reads 2026-05-10; 2026-09-04 is the layer-`/1`/`/3` date). `Type` is free "
        "text with about 40 spellings: creek 41, Spring 31, Dirt Tank 25, Structure 20, null 15, Dirt Stock "
        "Tank 13, Spigot 10… Layer `/1` Points: 3,041 (Milepost 1,664, Road Jct 467, Structure 258, Trail Jct "
        "252, Water 162, Trailhead 56, Bridge 13, Campground 10), with an `Elevation` field. Layer `/2` "
        "Trailheads: 106. PDFs: `.../2024/08/water-cache-box-locations-08152024.pdf` (bear-box water caches) "
        "and …",
    ),
    where=(
        "https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services",
        "https://aztrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
