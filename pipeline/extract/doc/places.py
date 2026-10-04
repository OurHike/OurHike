"""Dartmouth Outing Club: places, published as prose with no coordinate, and not landed (decision 54, wave 5,
read 2026-10-04). The Second College Grant and Moosilauke Ravine Lodge pages describe the college's lands and
lodge, with directions and no fix; the numbers the page carries are its SVG icons'. Marginal for a hiker's map
in the coverage audit's word (2026-10-01).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "outdoors.dartmouth.edu/robots.txt (Drupal's), then /facilities/second-college-grant, read 2026-10-04 under"
        " lib/user_agent.py's agent: 200, 79,551 bytes, no coordinate outside the page's SVG paths.",
        "the coverage audit (2026-10-01, batch c1_at_clubs_north): /facilities/moosilauke-ravine-lodge/directions "
        "and /facilities/second-college-grant, both pages.",
    ),
    where=("https://outdoors.dartmouth.edu/facilities/second-college-grant",),
    reason="needs a per-site reader, not built in this pull request: the lodge and the Grant are prose with directions, no coordinate",
)
