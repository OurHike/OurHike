"""Superior Hiking Trail Association: closures, from the trail-conditions page, hourly (decision 53 phase B,
2026-10-03).

`shta_trail_conditions` reads WordPress page 73 (https://superiorhiking.org/trail-conditions/) through
its REST route `/wp-json/wp/v2/pages/73`, which carries no query string, as one PageNotice
(extract/_notices.py's `wp_page`), read live under our agent on 2026-10-03 after the site's robots.txt
(`User-agent: *` / `Disallow:`, nothing disallowed). The page states 'Updated October 1, 2026', which
lands as the row's date; its rendered content (17,577 characters that day) is six map-series sections
and general corridor information, about 50 conditions: the I-35 pedestrian bridge closed until October,
the Lakewalk closed through November 2026, McCarthy Creek's bridge out, the Spirit Mountain spur's
winter closure. Nothing of its text lands. REST answers carry no HTTP validators (no-store).

Closures and crossing hazards share one list, so not_available.toml [shta.warnings] shares this file and dbt splits them
(decision 7). Each `/trail-section/` page's 'Trail Alerts' block (a seasonal wasp hazard, the coverage
audit) is a later per-page reader.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
c7_regional_4): "Page (HTML inside REST JSON). Reroute maps are JPG/PDF."
"""

from extract._kinds import page_notice

CLAIMS = ("shta_trail_conditions",)
RESOURCES = [page_notice("shta_trail_conditions", wp_page=73)]
