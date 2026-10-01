"""Nantahala Hiking Club: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c3_at_clubs_south).

These are a schedule of outings, not a route library. 301 of 360 descriptions contain phone numbers,
so strip them. (skeptic) The "Take a Hike with NHC" emails in the newsletter RSS (2026-09-03,
2026-08-19, 2026-08-07) carry the same hikes with "Hiking Distance", "Rating" and "Elevation
Gain/Loss" …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Public Google Calendar "NHC Hikes" (embedded on `/event-calendar/`), ICS at '
        "`https://calendar.google.com/calendar/ical/joklpibvni7mkss9oa5tjqnfao%40group.calendar.google.com/public/basic.ics`"
        " (machine-readable). It holds 360 events (2002-10-07 to 2026-10-28; 40 in 2026), with prose "
        "descriptions.",
    ),
    where=(
        "https://calendar.google.com/calendar/ical/joklpibvni7mkss9oa5tjqnfao%40group.calendar.google.com/public/basic.ics",
        "https://nantahalahikingclub.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
