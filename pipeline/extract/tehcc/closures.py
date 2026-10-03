"""Tennessee Eastman Hiking & Canoeing Club: closures, from the club's Appalachian Trail posts, hourly (decision
53 phase B, 2026-10-03).

`tehcc_at_posts` reads the 'Appalachian Trail' category (id 3) through WordpressPosts, read live under our
agent on 2026-10-03 after tehcc.org's robots.txt (`/wp-admin/` only): 87 posts by X-WP-Total, ids unique,
the newest modified 2025-09-09. The titles carry the facts ('Laurel Fork Shelter damaged by fire',
2024-08-15; 'Update: Clyde Smith Shelter reopened after temporarily closed due to bear activity',
2025-05-30; two 'A.T. Camping Closure' posts, 2023-02-23). MOSTLY HISTORIC: a 2023 camping closure is
not current, and expiry is dbt's rule. The posts' `content` and `excerpt` never load: they carried 14
telephone numbers that day (decision 59; the row's person_fields), and the bodies are members-only
anyway (the coverage audit: 12 of 87, every one since 2022-01-18). What lands is each post's title,
dates, categories and link. The category's RSS feed (/category/appalachian-trail/feed/, 10 items) is a
window of this list and is not read.

The Cherokee National Forest's alerts page, which the coverage audit read for the Watauga banner, lands
in usfs/closures.py as `usfs_r08_cherokee_alerts` (decision 34). The club's wiki announcements and its
maintenance log are warnings.py's.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
c3_at_clubs_south): "The Watauga banner looks stale. The Cherokee NF alerts page ... lists no Watauga,
Wilbur Dam or US 321 A.T. closure (Reasoned that it has lapsed; whether it still stands is
@unvalidated)."
"""

from extract._kinds import wordpress_posts

CLAIMS = ("tehcc_at_posts",)
RESOURCES = [wordpress_posts("tehcc_at_posts")]
