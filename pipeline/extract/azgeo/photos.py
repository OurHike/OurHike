"""AZGeo Data Hub: photos, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

2,678 photos of gates, signs and road crossings along the AZT are exactly the "what does this
junction look like" picture a hiker uses. Licence unstated, and the images sit on a contractor's
host, so `may_publish` stays false until the ATA (batch c10) answers. This goes in `ata/photos.py`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`ATA_StoryMap_PhotoPoints_Trail_Running_view/0`: 14 points with `pic_url` (2025-11-02). No licence.",
        "Skeptic adds (Measured): `Scenic_Resources_AGOL_view/FeatureServer` (owner `AZTrail`, last edit "
        "2026-09-04) is a geotagged photo inventory: `/0` Sign Inventory 2,117, `/1` Gate Inventory 305, `/2` "
        "Road Crossing Inventory 230, `/8` Other 26. Each row's `Link` is a JPEG, e.g. "
        '`https://www.giseifert.com/images/ATA_Scenic_Resources/IMG_001.jpg` (subject "Mexico Border"). '
        "`ATA_StoryMap_PhotoPoints_view/0` holds 174 more (the Trail Running view's 14 are a subset).",
    ),
    where=(
        "https://www.giseifert.com/images/ATA_Scenic_Resources/IMG_001.jpg",
        "https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services/Scenic_Resources_AGOL_view/FeatureServer",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
