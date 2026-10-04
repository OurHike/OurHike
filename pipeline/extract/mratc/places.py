"""Mount Rogers Appalachian Trail Club: places, a paragraph pointing elsewhere, and not landed (decision 54, wave
5, read 2026-10-04). The club's backpacking-rules page's PARKING paragraph names Damascus' public long-term
lots ('overnight parking up to 30 days') and links visitdamascus.org/parking/, the town's own page, which
describes the lots and a registration form with no coordinate.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "visitdamascus.org/robots.txt (Yoast's), then /parking/, read 2026-10-04 under lib/user_agent.py's agent: "
        "200, 207,734 bytes, the lots in prose and long_term_parking_registration_form.pdf; no coordinate in the "
        "page.",
        "the coverage audit (2026-10-01, batch c3_at_clubs_south): thin, one paragraph on /backpacking-rules.",
    ),
    where=(
        "https://visitdamascus.org/parking/",
        "https://www.mratc.org/backpacking-rules",
    ),
    reason="needs a per-site reader, not built in this pull request: the town's lots are prose with no coordinate",
)
