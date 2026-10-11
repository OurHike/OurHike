"""Washington State Parks and Recreation Commission: closures. The commission's trail_orgs.json row, `wa-parks` (`load:
via`, its lines RCO's), was approved on 2026-10-11 (decision 121, review page 02), so its two files moved here from
_shared/wa_state_parks/, the folder decision 53 phase B (2026-10-03) had named before the coverage audit's slug was
chosen, and became this one file. THE FOLDER'S NAME CHANGED WITH IT, as the row's review said it would ("which this row
would rename"), so both raw tables are renamed: raw_wa_state_parks__wsprc_alerts_page is now
raw_wa_parks__wsprc_alerts_page, and raw_wa_state_parks__wsprc_winter_rec_closures is now
raw_wa_parks__wsprc_winter_rec_closures, each first loaded under its new name by the run after this change. wa_rco/
and the clubs whose notes name these layers draw on them here (decision 34).

- `wsprc_alerts_page`: https://parks.wa.gov/about/news-announcements/alerts, every park's alerts in one Drupal
  listing (the coverage audit counted 234 on 2026-10-01), one PageNotice. The listing has no feed and no JSON, so the
  whole page is one notice and any alert's edit reads as a new version of it. Its title is held to 'Alerts'.
  parks.wa.gov's robots.txt asks no Crawl-delay (2026-10-09). Decision 122 (the maintainer's poll, 2026-10-09) loaded
  it held until the commission's row was approved (decision 121).
- `wsprc_winter_rec_closures`: WA State Parks winter recreation temporary closures,
  `Temporary_Closure_(Public)/FeatureServer/0`. Its row says why phase C should hold it back.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never loads. The layer's
change check is _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS Online, and an allowed zero
only beside the server's own returnCountOnly read in the same run.
"""

from extract._kinds import arcgis_layer
from extract._notices import page_notice

CLAIMS = ("wsprc_alerts_page", "wsprc_winter_rec_closures")
RESOURCES = [page_notice("wsprc_alerts_page", expect_title="Alerts"), arcgis_layer("wsprc_winter_rec_closures")]
