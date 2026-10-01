"""Ala Kahakai Trail Association: trail lines, published, and not landed (coverage audit 2026-10-01,
batch c11_nht).

The official geometry is a corridor polygon, not a line

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`NPSAGOL/Ala_Kahakai_National_Historic_Trail_Official_Corridor/0`: 1 polygon (corridor, 2025-12-05). "
        "`NPSAGOL/ALKA_Story_Maps`: lines Kohala Hema 14, Alanui Aupuni 1, Kaʻawaloa 1, Kīholo–Puakō 2. "
        '`nps_trails`: KAHO "Ala Kahakai Trail" 4 (LOADED fragment). Own: '
        "`https://www.alakahakaitrail.org/s/ALKA-MAP.pdf` (PDF)",
    ),
    where=("https://www.alakahakaitrail.org/s/ALKA-MAP.pdf",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
