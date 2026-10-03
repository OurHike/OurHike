"""Lone Star Hiking Trail Club: podcasts, nothing published (coverage audit 2026-10-01, batch
c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "No club show. Third party: Trailblazing Texas Podcast LSHT episodes (2024-10-31, 2026-05-21); "
        "Wandering Into The Woods S2E10 (2022-01-31).",
        "Skeptic: the nav has no audio item (Trails, Volunteer, Events, Membership, Donations, Information, "
        'Shop, News, Blogs, Helpful Links, About Us). The Apple directory searched by "Lone Star Hiking Trail" '
        "lists 15 shows, none of them the club's.",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://lonestartrail.org/",
    ),
)
