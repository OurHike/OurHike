"""AZGeo Data Hub: warnings, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check):
https://aztrail.org/wp-json/wp/v2/posts?categories=251&per_page=100&_fields=id,slug,date_gmt,modified_gmt,title,link,categories,tags
(wordpress); https://aztrail.org/category/closures-reroutes/feed/ (rss);
https://aztrail.org/wp-json/wp/v2/categories?slug=closures-reroutes&_fields=id,count,name,slug,link
(wordpress); https://aztrail.org/category/closures-reroutes/ (html_page).

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services/USFS_Camping_and_Campfire_Restricted_Area/FeatureServer/0,
a 2023 copy of a Coconino NF order (lastEditDate 2023-05-09); the Forest Service's own R3 order
layers in usfs/ are the live channel.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('The same feed\'s category is "Current Closures, Restrictions, and Reroutes" (org_channels). Items not read.',),
    where=(
        "https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services",
        "https://azgeo-open-data-agic.hub.arcgis.com/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
