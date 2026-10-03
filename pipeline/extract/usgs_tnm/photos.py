"""USGS — The National Map: photos, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Public domain, but off-topic: science imagery, not trail features.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "usgs.gov multimedia (images and audio) pages.",
        "Skeptic: `https://www.usgs.gov/products/multimedia-gallery/images` answers HTTP 200 to a browser user agent.",
    ),
    where=(
        "https://www.usgs.gov/products/multimedia-gallery/images",
        "https://usgs.gov",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
