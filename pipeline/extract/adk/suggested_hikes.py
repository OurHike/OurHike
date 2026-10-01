"""Adirondack Mountain Club: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

The skeptic made no requests to adk.org, because ADK's terms bar automated access. These URLs come
from a search engine's index and were not opened. Blog-style pages. The same written-permission gate
applies.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "A web search restricted to adk.org (2026-10-01) returns "
        '`https://adk.org/hiking-mount-jo-the-perfect-first-adirondack-summit/` ("just over two miles round '
        'trip with approximately 700 feet of elevation gain… two routes to the summit"), '
        "`https://adk.org/shoulder-season-hikes/` (Mount Jo, Goodman, Coney, Baxter, Mount Arab), and "
        '`https://adk.org/explore/first-time-visitor/` ("beginner-friendly hikes"). The guidebook "Peaks and '
        'Ponds" (37 day hikes) is sold.',
    ),
    where=(
        "https://adk.org/hiking-mount-jo-the-perfect-first-adirondack-summit/",
        "https://adk.org/shoulder-season-hikes/",
        "https://adk.org/explore/first-time-visitor/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
