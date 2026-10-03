"""Santa Fe Trail Association: places, published, and not landed (coverage audit 2026-10-01, batch
c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Own: `https://santafetrail.org/explore/`, a state-by-state list of NPS-certified sites (search "
        "snippet; page). Upstream: `NPSAPI/places` safe ≥70",
    ),
    where=("https://santafetrail.org/explore/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
