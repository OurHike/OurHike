"""DEC's suggested hikes are web pages and PDFs, under DEC's Website Content Usage policy, with no route data."""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "adirondack-day-hikes: about 40 unit headings and 124 mileage mentions",
        "catskill-hikes (about 27 hikes), hike-with-us-catskills, the four seasonal great-hikes pages, "
        "trails-less-traveled and first-day-hikes",
        "142 trail-map pages under /places-to-go/maps/: PDFs; no GPX and no route geometry anywhere",
    ),
    where=(
        "https://dec.ny.gov/things-to-do/hiking/adirondack-day-hikes",
        "https://dec.ny.gov/things-to-do/hiking/catskill-hikes",
    ),
    reason="web pages under DEC's Website Content Usage policy, outside the clearinghouse decision",
)
