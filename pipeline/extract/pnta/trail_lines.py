"""Pacific Northwest Trail Association: trail lines, drawn from usfs/'s resources (decision 34), registered
on 2026-10-03.

The PNT may exist in EDW in pieces under local trail names, and in `nps_trails` through Glacier,
North Cascades and Olympic (Reasoned, not checked). The R6 layer is the only whole-route geometry,
and it is nine years old with its own warning against this use. The display must say so. Skeptic: …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Live read 2026-10-03 (decision 54, wave 1): `usfs_pacific_northwest_trail` (456 lines) "
        "registered in sources.json and extracted in usfs/trail_lines.py. Its own licenseInfo says it 'is"
        " not intended for trip planning', so decision 38 holds it from publishing.",
        "No sources.json key carries the PNT. EDW has 0 segments named `PACIFIC NORTHWEST`, `PNT` or "
        "`PNNST`. USFS R6 publishes "
        "`https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services/Pacific_Northwest_National_Scenic_Trail/FeatureServer/0`"
        " (item `cc58868f580d4d608bff557d8c4687a0`): 456 segments, last edit 2017-04-04. Its licence "
        'reads: "not intended for trip planning or to determine public access along the trail… depicts '
        "the trail as it was designated and does not show current conditions or closures\". PNTA's own: "
        'none machine-readable. The catalogue\'s "GPX and KMZ downloads" were not …',
    ),
    where=(
        "https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services/Pacific_Northwest_National_Scenic_Trail/FeatureServer/0",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
