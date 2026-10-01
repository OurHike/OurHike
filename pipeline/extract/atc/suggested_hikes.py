"""ATC's 74 hike pages, refused by ATC's own terms until ATC gives written permission."""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "hikes-sitemap.xml: 74 pages in a `hikes` post type, newest lastmod 2026-08-19, each with difficulty, "
        "closest town, length, a description and driving directions",
        "7 sampled pages (max-patch, comers-creek-falls, pochuck-boardwalk, west-slope-of-hosner-mountain, "
        "laurel-fork-gorge-and-falls, kelly-knob, wachipauka-pond) carry coordinates, no GPX or KML",
        "ATC's website terms of 2025-11-21",
    ),
    where=(
        "https://appalachiantrail.org/hikes-sitemap.xml",
        "https://appalachiantrail.org/hikes/max-patch/",
    ),
    terms='"systematic or automated data collection" is forbidden without prior written permission',
)
