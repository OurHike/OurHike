"""US Fish & Wildlife Service: photos, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Federal works are generally public domain. Per-image credit was not checked.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`digitalmedia.fws.gov` redirects to `https://www.fws.gov/search/images`.",),
    where=(
        "https://www.fws.gov/search/images",
        "https://digitalmedia.fws.gov",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
