"""Connecticut DEEP: closures, 1 ArcGIS layer extracted here (decision 53 phase B, 2026-10-03).

- `ct_deep_property_access_status`: CT DEEP property access points: status,
  `DEEP_Property_Access_Locations/FeatureServer/0`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://ctparks.com/sitemap.xml (html_page);
https://portal.ct.gov/deep/state-parks/emergency-message---parks (html_page);
https://www.depdata.ct.gov/forestry/forestfire/firerpt.cshtml (html_page - robots.txt disallows it,
so not to be fetched).

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

from extract._kinds import arcgis_layer

CLAIMS = ("ct_deep_property_access_status",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
