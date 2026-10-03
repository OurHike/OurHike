"""Connecticut DEEP: closures, 1 ArcGIS layer extracted here (decision 53 phase B, 2026-10-03).

- `ct_deep_property_access_status`: CT DEEP property access points: status,
  `DEEP_Property_Access_Locations/FeatureServer/0`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

And 1 notice source read here (decision 53 phase B, 2026-10-03, pages, feeds and WordPress):

- `ct_deep_parks_emergency_message`: CT DEEP State Parks emergency message, one notice for the page
  (PageNotice). Where a statewide parks closure would appear. Empty on 2026-10-01 and 2026-10-03:
  the template's title and no message, which `region_chars` tells from a notice.

Not wired: the per-park alert blocks on ctparks.com's 96 park pages (https://ctparks.com/sitemap.xml
lists them with a <lastmod> each; Kettletown's carried 'the Pomeraug, Crest and Brook Trails are
closed' on 2026-10-03). One registry row a park would ask ctparks.com 96 times an hour, and no
reader here reads a sitemap's lastmod to fetch only the parks that moved; that reader is the next
step for this folder. Refused by robots.txt and never fetched:
https://www.depdata.ct.gov/forestry/forestfire/firerpt.cshtml (`User-agent: *` / `Disallow:
/forestry/forestfire/`, read by the decision 53 inventory, batch 2, 2026-10-03), which also answered
a CAPTCHA to the coverage audit.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://services1.arcgis.com/FjPcSmEFuDYlIdKC/arcgis/rest/services/Areas_Closed_to_Hunting/FeatureServer/0,
384 season-flag polygons saying which seasons apply where, not when;
https://services1.arcgis.com/FjPcSmEFuDYlIdKC/arcgis/rest/services/DEEP_Trails_Set/FeatureServer/3,
TRAILSTAT 'Needs Repair' on 3 of about 13,883 trails, an inventory flag rather than a closure (a
trail_lines layer).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Connecticut DEEP: closures, published, and not landed (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

These are static flags, not a notice feed. Where else DEEP announces park closures was not checked,
because the search budget ran out. That gap belongs in the folder's dated note.; Skeptic,
2026-10-01: checked, and the gap closes. DEEP State Parks runs a second site, `https://ctparks.com`
(Drupal) …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `DEEP_Property_Access_Locations` `STATUS`: Open 384 / Closed 1
(Kettletown State Park). `DEEP_Trails_Set/3` `TRAILSTAT` "Needs Repair": 3. The page
`https://portal.ct.gov/deep/state-parks/emergency-message---parks` was read and held no notice on
2026-10-01. The State Parks hub's 23 DEEP links include no closures page.

Its `where`: https://portal.ct.gov/deep/state-parks/emergency-message---parks https://ctparks.com
https://ctparks.com/media/2133/download?inline https://ctparks.com/sitemap.xml
https://ctparks.com/hiking https://portal.ct.gov/deep/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer, page_notice

CLAIMS = ("ct_deep_property_access_status", "ct_deep_parks_emergency_message")
RESOURCES = [arcgis_layer("ct_deep_property_access_status"), page_notice("ct_deep_parks_emergency_message")]
