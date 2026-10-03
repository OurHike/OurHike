"""Florida Trail Association: closures, 1 ArcGIS layer extracted here (decision 53 phase B,
2026-10-03).

- `fta_fnst_closed_segments`: Florida National Scenic Trail master: segments not open,
  `FNST%20Master/FeatureServer/0`. Filtered on the agency's own status field: `Open_Statu <> 'Open'
  OR Open_Statu IS NULL`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check):
https://floridatrail.org/wp-json/wp/v2/posts?categories=37,40,41,42,43 (wordpress);
https://floridatrail.org/category/closures-and-nth-north/feed/ (rss);
https://floridatrail.org/hiker-safety/ (html_page).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Florida Trail Association: closures, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

The categories mix closures with Notices to Hikers ("NTH"). By decision 7, an unclassified row goes
to warnings. Post titles carry FTA map-sheet numbers ("Maps 39-40"), not coordinates. Skeptic:
spot-checked `X-WP-Total: 14` for those five categories. The per-category counts add to 15, so one
post …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): WordPress REST
`https://floridatrail.org/wp-json/wp/v2/posts?categories=37,40,41,42,43`: categories
`closures-notice-to-hikers-general` (2), `closures-and-nth-panhandle` (3), `-north` (5), `-central`
(1), `-south` (4). 14 posts, 2018-07-01 to 2026-07-28 (newest: "Map 14 – Sugar Creek Closure along
Suwannee River"). There is an RSS feed per category, e.g.
`https://floridatrail.org/category/closures-and-nth-north/feed/` (200, `application/rss+xml`). The 3
`Open_Statu = Closed` segments above are a machine-readable closure.

Its `where`: https://floridatrail.org/wp-json/wp/v2/posts?categories=37,40,41,42,43
https://floridatrail.org/category/closures-and-nth-north/feed/ https://floridatrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("fta_fnst_closed_segments",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
