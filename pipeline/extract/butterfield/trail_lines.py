"""Butterfield Overland Trail Association: trail lines, drawn from nps/'s resources (decision 34),
registered on 2026-10-03.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Live read 2026-10-03 (decision 54, wave 1): `nps_butterfield_overland_nht` (1,748 lines), "
        "`nps_butterfield_srs_route` (2 lines) registered in sources.json and extracted in "
        "nps/trail_lines.py.",
        "`NPSAGOL/BUOV_Congressionally_Designated_Alignment/0`: 1,748 lines (2026-08-25; TRUSE "
        "Non-Motorized 1,728, Highway Vehicle 19, Hiker/Pedestrian 1). "
        '`NTIR_OTHER_ButterfieldOverlandTrailSRS_ln`: 2. `nps_trails`: FOBO "Butterfield Trail" 3 (LOADED'
        ' fragment). Own `/interactive-map/`: "Map Coming Soon!"',
    ),
    where=(
        "https://butterfieldtrail.org/",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/BUOV_Congressionally_Designated_Alignment/FeatureServer/0",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/NTIR_OTHER_ButterfieldOverlandTrailSRS_ln/FeatureServer/0",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
