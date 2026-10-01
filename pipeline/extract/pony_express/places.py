"""National Pony Express Association: places, published, and not landed (coverage audit 2026-10-01,
batch c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Own: `/historic-pony-express-trail/monuments-museums/` (statues and museums with addresses, HTML); "
        "`/the-states/<state>/` ×8. `NPSAPI/places` poex ≥58",
    ),
    where=("https://nationalponyexpress.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
