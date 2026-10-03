"""NC Division of Parks & Recreation: closures, from Mount Mitchell State Park's page, hourly (decision 53
phase B, 2026-10-03).

`nc_parks_mount_mitchell_alerts` reads the park's page as one PageNotice (extract/_notices.py), read live
under our agent on 2026-10-03 after www.ncparks.gov's robots.txt (Drupal internals only, no
Crawl-delay). The park's alert carousel (`#block-ncalertsblock`), 3 items that day, among them 'North of
the park, the Parkway is closed', sits in the page header before <main>, so the region is <body>: a hash
of the default <main> would not move when an alert does, which is a false FRESH on a closures source.
The block itself is not the region, because a park with no alerts may not render it, and a missing
region reads as a changed page. The row lands the page's <h1>, no date (the page states none) and a
hash of <body>, whose two reads that day hashed the same. `expect_title` holds the page to Mount
Mitchell's. The
carousel's classes (breaking, warning, info, success) do not say closure or warning, so the two are
split in dbt (decision 7) and warnings.py shares this file. nc.gov's terms permit non-commercial
copying "without alteration", which is decision 55's case (sources.json's row quotes them).

ONE PARK OF ABOUT 47. ncparks.gov's sitemap lists about 47 park roots, and the Mountains-to-Sea Trail
passes several (Eno River, Falls Lake, Stone Mountain among them, the coverage audit). Which parks the
build's trails cross is a reviewed list nobody has made, so only the park the inventory measured is
read; each other park is another registry row, never a guess at a slug. The sitemap's <lastmod> was
proposed as one change check for all of them (inventory, batch 1); the reader reads each page and
hashes it instead.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
c9_federal_state_rest): "Page, one per park (about 41 units). No feed or JSON found. Skeptic checked
`/jsonapi`, `/alerts` and `/park-alerts` (all 404) and `/rss.xml` (403)."
"""

from extract._kinds import page_notice

CLAIMS = ("nc_parks_mount_mitchell_alerts",)
RESOURCES = [page_notice("nc_parks_mount_mitchell_alerts", region="body", expect_title="Mount Mitchell")]
