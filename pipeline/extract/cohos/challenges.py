"""Cohos Trail Association: challenges, a hall of fame, and not landed (decision 54 wave 5, section K,
2026-10-04).

/cohos-trail-hall-of-fame/ lists completion 'firsts' (first woman, oldest, first winter traverse): people, a
roster, never read.

The note this replaces read, whole:

The Cohos Trail Association: challenges, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

A recognition list. Skeptic correction (M): "No patch or application found" is wrong. The store sells
`/product/certificate-of-completion/` (modified 2025-07-09), `/product/cohos-trail-finisher-plaque/`
("engraved with the words CT, NOBO/SOBO, and the year") and `/product/cohos-trail-patch/`. So a …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/cohos-trail-hall-of-fame/`: a list of completion "firsts" (first
woman, oldest, first winter traverse).

Its `where`: https://cohostrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) /cohos-trail-hall-of-fame/",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://cohostrail.org/cohos-trail-hall-of-fame/",),
    reason="a roster of people, never read; no list of places",
)
