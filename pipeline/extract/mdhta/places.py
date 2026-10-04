"""Maah Daah Hey Trail Association: places. Its 19 trailhead pages are the same trailheads as the trail guide's
anchors, which mdhta/points_of_interest.py loads as points with their fixes (`mdhta_trail_guide_points`,
decision 54 wave 5, read 2026-10-04): a trailhead is a point, not an area. The FAQ's campground-distance table
and North Dakota's high point (/white-butte-2/) are prose.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "mdhta.com/trailheads/bear-creek/, read 2026-10-04 under lib/user_agent.py's agent: 200, 32,774 bytes, the "
        "trailhead's directions and no coordinate of its own; the trail guide's anchor carries its fix.",
        "the coverage audit (2026-10-01, batch c8_regional_5): 19 trailhead pages (`wp-sitemap-posts-trailheads-1.xml`).",
    ),
    where=(
        "https://mdhta.com/trailheads/bear-creek/",
        "https://mdhta.com/trail-guide/",
    ),
    reason="loaded as points of interest: the trailheads are points, in the sibling points_of_interest.py",
)
