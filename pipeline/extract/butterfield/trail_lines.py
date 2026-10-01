"""Butterfield Overland Trail Association: trail lines, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`NPSAGOL/BUOV_Congressionally_Designated_Alignment/0`: 1,748 lines (2026-08-25; TRUSE Non-Motorized "
        "1,728, Highway Vehicle 19, Hiker/Pedestrian 1). `NTIR_OTHER_ButterfieldOverlandTrailSRS_ln`: 2. "
        '`nps_trails`: FOBO "Butterfield Trail" 3 (LOADED fragment). Own `/interactive-map/`: "Map Coming '
        'Soon!"',
    ),
    where=("https://butterfieldtrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
