"""PASDA / PA DCNR: warnings, published, and not landed (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

Hunting season matters on state forest trails. Spray blocks are a short-lived closure or warning
shape.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`agsprod/BOF/HuntStateForest/MapServer`, 11 layers including Bear Check Stations, Wildlife Management "
        "Units, Elk Hunt Zones, Roads Opened for Deer Season and Special CWD DMAP Units. "
        '`pasda/DCNR2/MapServer/9` "State Forest Gated Roads Open for Deer Season 202310": 308. '
        "`BOF/SpongyMothSprayBlocks` and `SpongyMothTwpStatus` (spray operations). Daily fire-danger PDFs "
        "(c17).",
    ),
    where=("https://mapservices.pasda.psu.edu/server/rest/services/pasda/DCNR2/MapServer/9",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
