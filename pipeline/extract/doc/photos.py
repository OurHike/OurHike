"""Dartmouth Outing Club: photos, drawn from another folder's resource (coverage audit 2026-10-01,
batch c1_at_clubs_north).

ATC permission basis.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("ATC `Photo1` on 7 of 7 DOC shelters. C&T's SmugMug `https://dartoutclub.smugmug.com/CnT` states no licence.",),
    where=("https://dartoutclub.smugmug.com/CnT",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
