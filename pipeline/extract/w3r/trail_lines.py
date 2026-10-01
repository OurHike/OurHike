"""National Washington-Rochambeau Revolutionary Route Association: trail lines, published, and not
landed (coverage audit 2026-10-01, batch c11_nht).

A driving route. The Esri and VDOT copies are not this org's

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`NPSAGOL/20200622_2016_URI_WARO_NST_trail_centerline_states_combined_web_mercator/0`: 11 lines "
        '(2025-05-30). `nps_trails`: 0. Esri Federal\'s "Washington Rochambeau National Historic Trail Route" '
        '(`an email address`) and VDOT\'s "Washington Rochambeau Auto Tour" exist',
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://w3r-us.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
