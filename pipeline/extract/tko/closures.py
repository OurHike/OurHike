"""Trailkeepers of Oregon: closures, from the Oregon Coast Trail's Trail Conditions posts, hourly (decision 53
phase B, 2026-10-03).

`tko_oct_trail_conditions` reads the 'Trail Conditions' category (id 10, slug 'trail-conditions') through
WordpressPosts, read live under our agent on 2026-10-03 after trailkeepersoforegon.org's robots.txt
(nothing these routes reach is disallowed): 2 posts by X-WP-Total, 'Recent Updates' (id 3502, modified
2026-08-25) and 'Additional Updates' (id 3573, modified 2026-08-31), each bundling many Oregon Coast
Trail items (a landslide closing the trail down the south side of Tillamook Head, North Cape Sebastian
"washed out at Daniels Creek", the Necarney Creek bridge out). REST's `modified` is the change signal,
never the category feed, which reports the 2025 publish dates (the coverage audit). The posts'
`content` and `excerpt` never load: they carried 3 telephone numbers that day (decision 59; the row's
person_fields), so what lands is each post's title, dates and link.

The posts carry warnings beside closures, so not_available.toml [tko.warnings] shares this file and dbt splits them (decision
7). Water outages in them belong to water-source attributes (decision 2), not warnings.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
c6_regional_3): "Use REST `modified`, not the RSS feed."
"""

from extract._kinds import wordpress_posts

CLAIMS = ("tko_oct_trail_conditions",)
RESOURCES = [wordpress_posts("tko_oct_trail_conditions")]
