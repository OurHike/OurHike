"""PASDA / PA DCNR: challenges, published, and not landed (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

This is a DCNR-run end-to-end programme with a reward, the #1780 shape. Caveat: the cache
coordinates live on geocaching.com, whose terms govern them (not read), so the extractable content
is the 25 park names, themes, hike lengths and GC codes. The park centroids come from DCNR's own …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"DCNR GeoTrail: Celebrating America\'s 250th", '
        "`https://www.pa.gov/agencies/dcnr/recreation/what-to-do/geocaching/dcnr-geo-trail` (200, read "
        "2026-10-01). It is run with America250PA.",
        "25 geocaches, one per location: state parks and environmental education centres, for example "
        "Beltzville, Benjamin Rush, Black Moshannon, Jennings EEC and White Clay Creek Preserve.",
        'Each location gives a theme, the hike length and terrain (for example "1-mile round trip over uneven '
        'terrain"), and a geocaching.com GC code, from `GCBJH8G` onward. There are 25 distinct codes on the '
        "page.",
        '"If you complete all …',
    ),
    where=(
        "https://www.pa.gov/agencies/dcnr/recreation/what-to-do/geocaching/dcnr-geo-trail",
        "https://geocaching.com",
        "https://mapservices.pasda.psu.edu/server/rest/services/pasda/DCNR/MapServer/8",
        "https://pasda.psu.edu/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
