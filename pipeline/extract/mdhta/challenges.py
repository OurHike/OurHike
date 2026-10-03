"""Maah Daah Hey Trail Association: challenges, published, and not landed (coverage audit 2026-10-01,
batch c8_regional_5).

Page. A tiered mileage challenge, not a place list.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"2026 MDH Trail Challenge", `https://mdhta.com/2024-mdh-trail-challenge/`: "Challenge miles can be '
        'earned from using any of the trails in the Maah Daah Hey Trail System", self-reported on a '
        "downloadable mileage log.",
        'Skeptic, re-read: "a patch for 25, 50, 100 or 150 will be awarded … For those completing 100 or 150 '
        'miles a sticker and patch". The site sometimes sends `content-encoding: gzip` to a request with no '
        "`Accept-Encoding`. I saw it on 3 requests, while an earlier `/trail-guide/` fetch came back plain. So "
        "a loader must always decompress.",
    ),
    where=(
        "https://mdhta.com/2024-mdh-trail-challenge/",
        "https://mdhta.com/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
