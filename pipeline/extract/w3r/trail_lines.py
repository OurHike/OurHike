"""National Washington-Rochambeau Revolutionary Route Association: trail lines, drawn from nps/'s resources
(decision 34), registered on 2026-10-03.

A driving route. The Esri and VDOT copies are not this org's

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Live read 2026-10-03 (decision 54, wave 1): `nps_washington_rochambeau_nht` (11 lines) "
        "registered in sources.json and extracted in nps/trail_lines.py.",
        "`NPSAGOL/20200622_2016_URI_WARO_NST_trail_centerline_states_combined_web_mercator/0`: 11 lines "
        "(2025-05-30). `nps_trails`: 0. Esri Federal's \"Washington Rochambeau National Historic Trail "
        'Route" (`an email address`) and VDOT\'s "Washington Rochambeau Auto Tour" exist',
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://w3r-us.org/",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/20200622_2016_URI_WARO_NST_trail_centerline_states_combined_web_mercator/FeatureServer/0",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
