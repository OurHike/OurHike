"""Laurel Highlands Hiking Trail (PA DCNR): challenges, nothing published (coverage audit 2026-10-01,
batch c9_federal_state_rest).

Verdict kept. If PPFF ever gets a catalogue row, the passport is its challenge, not DCNR's.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The LHHT page mentions no patch or end-to-end program. The "See Them All" State Parks & Forests '
        "Passport belongs to the Pennsylvania Parks & Forests Foundation (`paparksandforests.org`), a partner, "
        "not DCNR.",
        "Skeptic re-checked: a search for an LHHT end-to-end patch or certificate finds only the Laurel "
        "Highlands Trail patch sold in Keystone Trails Association's store "
        "(`ktahike.app.neoncrm.com/np/clients/ktahike/product.jsp?product=31`). That is a souvenir for sale, "
        "not a completion award, and it is KTA's.",
    ),
    where=(
        "https://paparksandforests.org",
        "https://ktahike.app.neoncrm.com/np/clients/ktahike/product.jsp?product=31",
    ),
)
