"""Old Spanish Trail Association: trail lines, drawn from blm/'s resources (decision 34), registered on
2026-10-03.

`OSNHT_Trails` is the walkable set. Prefer it to the alignment

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Live read 2026-10-03 (decision 54, wave 1): `blm_old_spanish_nht_trails` (101 lines), "
        "`blm_old_spanish_nht_alignment` (7 lines) registered in sources.json and extracted in "
        "blm/trail_lines.py. NPS's single 1:500,000 feasibility-study line of the trail is nps/'s "
        "`nps_old_spanish_nht`.",
        "`BLMEGIS/OSNHT_MM_Framework/FeatureServer/8` OSNHT_Trails: 101 lines with Trail_Name, Trail_Type"
        " and Trail_Surface_Type, edited 2026-01-30. `/10` alignment: 7. `/9` auto routes: 80. "
        "`NPSAGOL/OLSP_NHT/FeatureServer/0`: 1 line at 1:500k (2017). `nps_trails`: 1 AZRU feature. "
        "OSTA's \"download maps by county for ArcGIS Field Maps\" (search snippet) are BLM's Mobile Map "
        "Packages (`an email address`, about 14 county packages)",
    ),
    where=(
        "https://services1.arcgis.com/KbxwQRRfWyEYLgp4/arcgis/rest/services/OSNHT_MM_Framework/FeatureServer/8",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/OLSP_NHT/FeatureServer/0",
        "https://services1.arcgis.com/KbxwQRRfWyEYLgp4/arcgis/rest/services/OSNHT_MM_Framework/FeatureServer/10",
    ),
    reason="drawn from blm/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
