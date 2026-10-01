"""National Washington-Rochambeau Revolutionary Route Association: places, published, and not landed
(coverage audit 2026-10-01, batch c11_nht).

`NPSAPI/places` returned 0 for waro in the first 500

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('Own: state pages `w3r-us.org/md/`, `/ct/`, `/va/`, `/ny/` and "Trail History: Hub" (search index; pages)',),
    where=(
        "https://w3r-us.org/md/",
        "https://w3r-us.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
