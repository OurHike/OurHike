"""Nez Perce (Nee-Me-Poo) Trail Foundation: closures, drawn from usfs/closures.py's alerts page for the
trail (decision 53 phase B, 2026-10-03).

The Nez Perce National Historic Trail's alerts page is the Forest Service's, so it lands once, in
usfs/closures.py as `usfs_nez_perce_nht_alerts` (decision 34), and this club's portion is that page.
The Foundation's own site (nezpercetrail.net) holds one post, from 2014 (decision 53's inventory,
batch 5).

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
c11_nht): "Format is a page. No feed was found (Unvalidated whether the new fs.usda.gov site exposes
one)", and its `checked` named the same page with "No Featured Alerts at this Time".
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "usfs/closures.py `usfs_nez_perce_nht_alerts` reads https://www.fs.usda.gov/trails/nez-perce-nht/alerts "
        "(decision 53 phase B, 2026-10-03): 0 alert cards beside the four-card level legend, the page stating "
        "'No Featured Alerts at this Time', on two reads that hashed the same.",
        "(coverage audit, 2026-10-01) the same page: Key Critical / Fire Restriction / Caution / Information, "
        "'No Featured Alerts at this Time'.",
        "(decision 53 inventory, batch 5, 2026-10-03) nezpercetrail.net: one post, from 2014.",
    ),
    where=(
        "https://www.fs.usda.gov/trails/nez-perce-nht/alerts",
        "https://nezpercetrail.net/",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the page this org's notices arrive in",
)
