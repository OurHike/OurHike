"""Avenza: georeferenced PDF maps sold per publisher, refused.

The terms forbid automated access, and SOURCE_REGISTRY.md refuses the PDF
format on re-readability grounds anyway. Agency maps on Avenza have been
frozen since April 2026, so a source that sends hikers there for a current
motor vehicle use map is now stale (coverage audit, batch
c12_umbrella_route_aggregator).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`sitemap.xml`: 879 product sitemaps, the first holding 993 product URLs, every one a georeferenced PDF map "
        "(coverage audit, batch c12_umbrella_route_aggregator)",
    ),
    where=("https://store.avenza.com/",),
    terms="commercial, per publisher",
)
