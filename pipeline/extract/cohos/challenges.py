"""The Cohos Trail Association: challenges, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

A recognition list. Skeptic correction (M): "No patch or application found" is wrong. The store
sells `/product/certificate-of-completion/` (modified 2025-07-09),
`/product/cohos-trail-finisher-plaque/` ("engraved with the words CT, NOBO/SOBO, and the year") and
`/product/cohos-trail-patch/`. So a …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('`/cohos-trail-hall-of-fame/`: a list of completion "firsts" (first woman, oldest, first winter traverse).',),
    where=("https://cohostrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
