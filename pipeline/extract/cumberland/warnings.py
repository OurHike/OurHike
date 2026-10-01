"""Cumberland Trail / Tennessee State Parks: warnings, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

Alert type codes 1/2/3 have no published legend. The mapping to closures and warnings is Unvalidated
until somebody reads a sample of each. Skeptic: today's split is type 3: 61, type 2: 16, type 1: 2.
Alert 199, "Park Closed Due to Construction", is type 3, the same code as alert 177's "Need to …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/api/alerts` alert 177 "Cumberland Trail Need to Know" (type 3): "exercise extreme caution while '
        'enjoying creek areas, including waterfalls. Water levels may change suddenly…". CTSST hazards with '
        '`H_C=\'H\'`: "Bridge badly damaged … use caution"; "old and poorly marked … needs ReBlazing".',
    ),
    where=("https://tnstateparks.com/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
