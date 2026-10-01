"""Bay Area Ridge Trail Council: challenges, published, and not landed (coverage audit 2026-10-01,
batch c6_regional_3).

A section-completion programme over a published segment layer. It is a close fit for #1780.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Circumnavigation (`/circumnavigation/`): every dedicated section, "over 400 miles", with a finisher '
        "form, certificate and wall of fame. The Circumnavigator category has 9 posts. 2026 Ridge Trail "
        "Challenge (`/2026-ridge-trail-challenge/`): complete 5 sections by 2026-12-31. Both are HTML.",
    ),
    where=("https://ridgetrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
