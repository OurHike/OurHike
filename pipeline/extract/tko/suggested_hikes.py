"""Trailkeepers of Oregon: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c6_regional_3).

The largest hike collection in the batch. The Field Guide part is blocked on its terms. The blog
posts are on `trailkeepersoforegon.org`, which states no terms, so the Field Guide's permission
notice does not cover them (Reasoned: a different site and a different notice). They are a small
hike …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Oregon Hikers Field Guide `Category:Hikes`: 1,736 pages (MediaWiki API, wikitext). Siteinfo: 8,322 "
        "articles and 22,836 images. Also OCT `/day-hiking/` (HTML, about 8 named hikes).; Added by skeptic, "
        "not under the Field Guide terms: TKO's own blog, category `oregon-hikers-spring-fundraiser` (id 40, 12"
        ' posts), holds 6 hike-description posts from 2026. They are "Four Hikes in the Columbia Gorge" '
        '(2026-05-04), "Four Hikes on the Oregon Coast" (05-11), "Three Hikes in the Willamette Valley" '
        '(05-18), "Three Hikes in Urban Areas" (05-26), "Special Hiking Guide: Mount Pisgah" (05-26) and "Four '
        "Hikes …",
    ),
    where=(
        "https://trailkeepersoforegon.org",
        "https://trailkeepersoforegon.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
