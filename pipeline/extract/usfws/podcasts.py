"""US Fish & Wildlife Service: podcasts, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

National conservation programming, not trail audio. Low value to a hiker.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'fws.gov podcast pages: "The Future of Conservation" (2026 series), Nature\'s Infrastructure, NCTC podcasts.',
        "Skeptic adds the exact URLs (HTTP 200 on 2026-10-01): "
        "`https://www.fws.gov/page/future-conservation-podcast-series` (page; episodes link to Apple Podcasts "
        "show `id1789144144`) and "
        "`https://www.fws.gov/library/collections/podcasts-national-conservation-training-center`. Neither page"
        " links an RSS URL. The feed behind the Apple show was not looked up.",
    ),
    where=(
        "https://www.fws.gov/page/future-conservation-podcast-series",
        "https://www.fws.gov/library/collections/podcasts-national-conservation-training-center",
        "https://fws.gov",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
