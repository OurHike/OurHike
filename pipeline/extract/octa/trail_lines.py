"""Oregon-California Trails Association: trail lines, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Both are traces of historic routes, not a maintained tread (finding 2). OCTA's own lines are GPS
field mapping per its NW chapter newsletter (search snippet), and so are the more precise geometry.
The licence is unstated, so `licence_basis` would read `unstated`

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`NPSAGOL/OREG_NHT/FeatureServer/0`: 1 line, 1:100k, edited 2019-03-04. "
        "`NPSAGOL/CALI_NHT/FeatureServer/0`: 1 line, edited 2025-05-30. `nps_trails` has 0 under OREG/CALI. "
        "Own: `services6.arcgis.com/RyWFDAB3oVbYYzSx/arcgis/rest/services`, 34 services, e.g. "
        "`Hastings_Cutoff_WFL1/9` Route (375 lines, 2026-07-09), `Naches_Pass_Trail_2020_0301` (83 lines), and "
        "Oregon Trail / Barlow Road / Meek / Klamath-Fremont segments named by atlas page. Item `afa4e581…` "
        "states no licence. Also: printed Trail Maps for sale at `octa-trails.org/product-category/trail-maps/`"
        " (search index)",
    ),
    where=(
        "https://services6.arcgis.com/RyWFDAB3oVbYYzSx/arcgis/rest/services",
        "https://octa-trails.org/product-category/trail-maps/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
