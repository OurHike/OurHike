"""New Mexico Volunteers for the Outdoors: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c6_regional_3).

Machine-readable through REST, as HTML bodies. The CONDITIONS sections are 2020–2023 snapshots. They
must never feed warnings or closures, and a hike card must show their date. No terms page.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Hike New Mexico" trail guide, `https://nmvfo.org/trails/` (WordPress page id 2040, modified '
        "2023-01-31). Its children come through "
        "`https://nmvfo.org/wp-json/wp/v2/pages?parent=2040&per_page=100` (`X-WP-Total` = 38). 35 of them carry"
        " the same four sections: SUMMARY, DESCRIPTION, GETTING THERE and CONDITIONS. They cover Cibola, Santa "
        "Fe and Gila NF trails, Albuquerque Open Space, BLM, and long trails (CDT, Grand Enchantment Trail, "
        'Northern New Mexico Loop). Example, Skyline Trail #251: "8.3k feet to 12.5k feet, 73.8 miles", with '
        'CONDITIONS "As of July 2020 Skyline is completely cleared of …',
    ),
    where=(
        "https://nmvfo.org/trails/",
        "https://nmvfo.org/wp-json/wp/v2/pages?parent=2040&per_page=100",
        "https://nmvfo.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
