"""National Mormon Trails Association: trail lines, drawn from nps/'s resources (decision 34), registered
on 2026-10-03.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Live read 2026-10-03 (decision 54, wave 1): `nps_mormon_pioneer_nht` (1 line) registered in "
        "sources.json and extracted in nps/trail_lines.py.",
        "`NPSAGOL/MOPI_NHT/0`: 1 line, 1:100k (2025-08-04). `nps_trails`: 0. Own `/maps/`, `/maps-2/` and"
        ' `/interactive-map/` read "COMING SOON"',
    ),
    where=(
        "https://mormontrails.org/",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/MOPI_NHT/FeatureServer/0",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
