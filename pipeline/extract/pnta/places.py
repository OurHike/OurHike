"""Pacific Northwest Trail Association: places, published, and not landed (coverage audit 2026-10-01,
batch c10_nst_rest).

Page. Skeptic spot-check: `/pnta/know-before-you-go/plan-your-trip/trail-towns-resupply/` returns
200. The overview-map PDF's "Trail Town/ Resupply Point" symbols (see points_of_interest) are the
same towns in map form.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`/trail-towns-resupply/`, `/backcountry-permits/`, `/permits-fees/`.",),
    where=("https://pnt.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
