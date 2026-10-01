"""Carolina Mountain Club: warnings, published, and not landed (coverage audit 2026-10-01, batch
c3_at_clubs_south).

Thin and prose-only. One trail item in five posts. (skeptic) The five WP posts are not the whole
run: `https://carolinamountainclub.org/e-news-archive/` (page builder; REST `content` is empty, so
read the HTML) links 34 eNews PDFs, 2024-01 to 2026-07 …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Monthly eNews posts (WP REST `/wp-json/wp/v2/posts`, category eNews id 59, 5 posts, 2026-01 to "
        '2026-05). "2026 February eNews" describes flood damage to "the bottom of a masonry staircase rising '
        'from Green Corner Road on the Appalachian Trail" near Snowbird Mountain.',
    ),
    where=(
        "https://carolinamountainclub.org/e-news-archive/",
        "https://carolinamountainclub.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
