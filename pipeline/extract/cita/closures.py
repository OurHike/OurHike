"""Central Iowa Trail Association: closures, published, and not landed (coverage audit 2026-10-01,
batch c5_regional_2).

The only live, structured open/closed source in this batch. The days-since-update figure must travel
with each row, because a 463-day-old "closed" is not a current fact. (Skeptic, 2026-10-01: same
verdict, better format. JSON API `/api/v1/status/{CITA|CITA-OTHER}/{code}` gives …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://status.centraliowatrails.com/`, server-rendered HTML. Each of 8 CITA areas plus 2 non-CITA "
        'areas has a `<div class="badge open|closed">CODE`, a condition word, and days since the last update. '
        "Snapshot 2026-10-01 ~03:30 UTC: CITA open BAN, CEN, DEN; closed EWG, FOUR, FLOW, GRA, SYC. Non-CITA "
        'AQB closed (463 d since update), WRC open (162 d). `/fourmilemtb`: "freeze/thaw or heavy rains cause '
        'the trails to close".',
    ),
    where=(
        "https://status.centraliowatrails.com/",
        "https://bikecita.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
