"""Connecticut DEEP: photos, could not be told (coverage audit 2026-10-01, batch b5_nyc_nj_ct_ma_pa).

Skeptic, 2026-10-01: UNKNOWN kept. An org search for "photo" returns 29 items, all coastal oblique
aerials (2003), habitat layers or a Survey123 outreach form, none a feature-photo layer.
`ctparks.com` serves park images with no licence statement and asks for `#CTStateParks` Instagram
tags. Flickr …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("504 AGOL service names were listed, and none is a photo layer. The website's image terms were not read.",),
    where=(
        "https://ctparks.com",
        "https://portal.ct.gov/deep/",
        "https://services1.arcgis.com/FjPcSmEFuDYlIdKC/arcgis/rest/services",
    ),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
