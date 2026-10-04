"""Butterfield Overland Trail Association: points of interest, published, and not landed (coverage
audit 2026-10-01, batch c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Decision 54, wave 3 (2026-10-04): the NPS API list this note names is /visitorcenters, which is not
registered yet.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "the NPS Data API's /visitorcenters is not registered: it answered 429 OVER_RATE_LIMIT on api.data.gov's public demo key on 2026-10-04, so nothing of it was read (decision 54, wave 3).",
        "`NPSAPI/visitorcenters` buov 1. NTIR POIs have no `buov` flag",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://butterfieldtrail.org/",
    ),
    reason="published and not landed: the NPS API's /visitorcenters is not registered (no read with a real key yet)",
)
