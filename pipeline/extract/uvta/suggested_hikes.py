"""Upper Valley Trails Alliance: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

PDF only. Skeptic, 2026-10-01 (M): the full paths are
`wp-content/uploads/2019/09/Suggested-hiking-venues-…pdf` (a guessed `/2019/08/` path 404s), and the
WP media endpoint lists a newer `wp-content/uploads/2025/12/Spike-Hikes-Updated.pdf` (dated
2025-12-04) beside the 2022 one.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "PDFs linked from uvtrails.org: `Suggested-hiking-venues-in-the-Upper-Valley-2019-08-02.pdf`, "
        "`Spike-Hikes-Updated.pdf` (2022), `Chasing-Waterfalls-Guide-0506-1.pdf` (2025-05), "
        "`Mud-Season-Guide.pdf`.",
    ),
    where=("https://uvtrails.org",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
