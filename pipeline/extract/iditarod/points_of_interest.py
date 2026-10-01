"""Iditarod Historic Trail Alliance: points of interest, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Shelters, as PDF only. Contains no coordinates, from a text read

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Iditarod NHT Visitor Guide, "
        "`https://www.iditarod100.org/uploads/5/2/4/5/52459009/iditarodnhtvisitorguide.pdf` (PDF, 11,786,538 "
        'bytes, Last-Modified 2024-04-05, published by Alaska Geographic with BLM): "Public Shelter Cabins" on '
        'p.17, spaced "about twenty miles apart"; Chugach NF rental cabins on Johnson Pass and Crow Pass via '
        "recreation.gov",
    ),
    where=(
        "https://www.iditarod100.org/uploads/5/2/4/5/52459009/iditarodnhtvisitorguide.pdf",
        "https://recreation.gov",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
