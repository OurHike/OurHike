"""Lewis and Clark Trust: photos, published, and not landed (coverage audit 2026-10-01, batch c11_nht).

Terrain360 imagery shows no open licence. Not openly licensed

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`NPSAPI/multimedia/galleries` lecl 8. Own: Terrain360 panoramas (Katy Trail 360°, Mississippi River "
        "360°). NPS indexes 206,076 panorama points at "
        "`NPSAGOL/Lewis___Clark_National_Historic_Trail_both_detailed_20250421155752/0`, imagery hosted at "
        "`d36h3klmd6060l.cloudfront.net` (Terrain360, a commercial company)",
    ),
    where=("https://d36h3klmd6060l.cloudfront.net",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
