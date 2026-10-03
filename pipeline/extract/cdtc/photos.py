"""Continental Divide Trail Coalition: photos, nothing published (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "No openly licensed photo set among the 133 items. The StoryMaps are photo tours with no licence; "
        "`Gateway_Communities.ImageLink` states none.",
        "Skeptic adds: `Gateway_Communities_2026_view/0` has `ImageLink` filled on 19 of 27 rows, and the two "
        "sampled point at `cdtcoalition.org/wp-content/uploads/CDT_Postcards5.jpg` and `…Postcards3.jpg`. Those"
        " are postcard artwork, not photos of features (Measured).",
    ),
    where=("https://cdtcoalition.org/wp-content/uploads/CDT_Postcards5.jpg",),
)
