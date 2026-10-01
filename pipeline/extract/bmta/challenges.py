"""Benton MacKaye Trail Association: challenges, published, and not landed (coverage audit 2026-10-01,
batch c8_regional_5).

The finisher table is people's names. Ingest the programme, never the list.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'End-to-end recognition through a "Completion Report & Request for Listing" '
        "(`/thru-hikers-guide/#milers`). The BMTA sends one patch plus a Thru-Hike, 300-, 500- or 1,000-Mile "
        "rocker (`/product/trail-patch/`).",
        "Skeptic: `product-sitemap.xml` lists `trail-patch/`, `thru-hiker-crescent/`, `300-miler-rocker/`, "
        "`500-miler-crescent/` and `1000-miler-crescent/`. So 300 is a rocker, and thru-hike, 500 and 1,000 are"
        " crescents. The `100-hour-club` and `50-miler-hike-leader` award forms in the page sitemap are "
        "volunteer awards, not hiker challenges.",
    ),
    where=("https://bmta.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
