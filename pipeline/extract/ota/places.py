"""Ozark Trail Association: places, published as lists with no coordinate, and not landed (decision 54, wave 5,
read 2026-10-04). The trail services page lists shuttles, resupply and lodging, each tagged with the sections
it serves, with no fix; land managers and emergency numbers sit on the section pages (the coverage audit,
2026-10-01). The 72 trailheads are loaded through the association's My Map (ota/trail_lines.py).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "ozarktrail.com/robots.txt (WooCommerce's paths and /wp-admin/ disallowed), then /trail-services/, read "
        "2026-10-04 under lib/user_agent.py's agent: 200, 268,479 bytes, no coordinate in the page.",
        "the coverage audit (2026-10-01, batch c7_regional_4): /trail-services/, /list-of-contacts/ (land managers).",
    ),
    where=("https://ozarktrail.com/trail-services/",),
    reason="needs a per-site reader, not built in this pull request: services tagged by section, with no coordinate",
)
