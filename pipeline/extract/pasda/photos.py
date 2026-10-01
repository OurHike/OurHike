"""PASDA / PA DCNR: photos, could not be told (coverage audit 2026-10-01, batch b5_nyc_nj_ct_ma_pa).

Skeptic, 2026-10-01: UNKNOWN kept, and it leans closed. `FLICKR_LIN` holds Flickr album ids (sample
`72157635463973503`). Which account owns them is not confirmed: the album URL under `padcnr`
answered 403. DCNR's Flickr account is `https://www.flickr.com/photos/padcnr/` (`realname` "Pa DCNR"
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`pasda/DCNR2/MapServer/27` has `FLICKR_LIN`. c9 found `MustSeeParkPics` and other photo services with no licence.",
    ),
    where=(
        "https://www.flickr.com/photos/padcnr/",
        "https://mapservices.pasda.psu.edu/server/rest/services/pasda/DCNR2/MapServer/27",
    ),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
