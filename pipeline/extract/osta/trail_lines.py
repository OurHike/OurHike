"""Old Spanish Trail Association: trail lines, published, and not landed (coverage audit 2026-10-01,
batch c11_nht).

`OSNHT_Trails` is the walkable set. Prefer it to the alignment

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`BLMEGIS/OSNHT_MM_Framework/FeatureServer/8` OSNHT_Trails: 101 lines with Trail_Name, Trail_Type and "
        "Trail_Surface_Type, edited 2026-01-30. `/10` alignment: 7. `/9` auto routes: 80. "
        "`NPSAGOL/OLSP_NHT/FeatureServer/0`: 1 line at 1:500k (2017). `nps_trails`: 1 AZRU feature. OSTA's "
        '"download maps by county for ArcGIS Field Maps" (search snippet) are BLM\'s Mobile Map Packages (`an '
        "email address`, about 14 county packages)",
    ),
    where=(
        "https://services1.arcgis.com/KbxwQRRfWyEYLgp4/arcgis/rest/services/OSNHT_MM_Framework/FeatureServer/8",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/OLSP_NHT/FeatureServer/0",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
