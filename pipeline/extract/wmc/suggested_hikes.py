"""Wasatch Mountain Club: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

The reports are written by members and carry no licence. Faint Trails is login-gated (see above).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/trip-reports` is a public HTML listing of 551 table rows, dated 2006-09-16 to 2026-09-27. `/hiking` "
        "lists upcoming hikes with WMC ratings. (Changed by skeptic: verdict kept, best source changed from a "
        "page to machine-readable files. (1) 156 GPX / 157 KMZ route tracks, as in the trail_lines row. (2) "
        "`https://www.wasatchmountainclub.org/hike/WMCHikesCopyToWeb.xlsx` (66,121 bytes, Last-Modified "
        "2023-06-15), with the same table as a PDF, `WMCHikesCopyToWeb.pdf`. (3) Hike-ratings tables: "
        "`/dan-smiths-hike-ratings-table`, five sorted PDFs …",
    ),
    where=("https://www.wasatchmountainclub.org/hike/WMCHikesCopyToWeb.xlsx",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
