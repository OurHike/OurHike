"""PASDA / PA DCNR: closures, published, and not landed (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

A live re-route on a trail this project draws, published only as a page. Skeptic, 2026-10-01:
re-probed, so this is now Measured by this batch too.
`https://www.pa.gov/agencies/dcnr/recreation/where-to-go/state-forests/find-a-forest/tioga/advisories`
(200) still carries "Pine Creek Rail Trail at …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "c9 and c17 Measured this on 2026-10-01; I did not re-probe it. The pa.gov AEM alert fragments, "
        "`…/get-alert-by-path; alertPath=…`. The per-forest `…/advisories` pages, for example Tioga's \"Pine "
        "Creek Rail Trail at the bridge over Asaph Run will be re-routed starting on Monday, August 24th, "
        '2026". The ParkAdvisory JSON (`IsAlert`).',
    ),
    where=(
        "https://www.pa.gov/agencies/dcnr/recreation/where-to-go/state-forests/find-a-forest/tioga/advisories",
        "https://pa.gov",
        "https://www.pa.gov/en.sitemap.xml",
        "https://pasda.psu.edu/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
