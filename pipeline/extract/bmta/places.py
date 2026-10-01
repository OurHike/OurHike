"""Benton MacKaye Trail Association: places, published, and not landed (coverage audit 2026-10-01,
batch c8_regional_5).

Page.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/thru-hikers-guide/#resupply`: lodging, food, post offices and shuttles by mile, from mile 18.5 to 286.2.",
        "Skeptic, new: `/trail-town-communities/` names 3 designated BMT Trail Town Communities: Blue "
        'Ridge/Fannin County GA ("On April 13, 2013, Blue Ridge was named…"), East Ellijay/Ellijay/Gilmer '
        "County GA, and Tellico Plains/Monroe County TN.",
    ),
    where=("https://bmta.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
