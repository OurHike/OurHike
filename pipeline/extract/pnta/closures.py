"""Pacific Northwest Trail Association: closures, published, and not landed (coverage audit 2026-10-01,
batch c10_nst_rest).

Page, but tabular, with a miles-closed column. One row reads "0 miles" (reopened), and that one must
be read as an opening. Skeptic: spot-checked 1 table, a header plus 7 rows. The page reads "Last
Updated: August 27, 2026", which is the date to carry. Two `Miles Closed` cells are not clean …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://www.pnt.org/pnta/know-before-you-go/plan-your-trip/trail-alerts/`: one HTML `<table>` with 7 "
        'closure rows. Columns: State, Area, Miles Closed, Description, Detour, More Info. Example: "Section 6,'
        ' Pasayten Wilderness — 60 miles — Ptarmigan fire". WP category `trail-conditions`: 4 posts. WordPress '
        "REST is available.",
    ),
    where=(
        "https://www.pnt.org/pnta/know-before-you-go/plan-your-trip/trail-alerts/",
        "https://pnt.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
