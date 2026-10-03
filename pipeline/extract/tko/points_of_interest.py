"""Trailkeepers of Oregon: points of interest, published as hikes rather than points.

TKO's public ArcGIS layer, OregonHikers_Featured_Hikes_PublicView, is 4,069 featured-hike points with a title,
a link to the Oregon Hikers Field Guide page and up to six image links: the suggested_hikes type, not this one,
so it is not registered as a point layer here. The Field Guide's trailhead pages sit behind its terms, which
the coverage audit found block the MediaWiki route.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "OregonHikers_Featured_Hikes_PublicView/FeatureServer/0, 4,069 points, GlobalID unique (4,069 of "
        "4,069), fields title, name, url, latitude, longitude and Image1 to Image6, last edited 2021-09-11; a"
        " view of OregonHikers_Featured_Hikes (read 2026-10-03)",
        "the coverage audit's read (2026-10-01): the Field Guide's Category:Trailheads holds 1,738 pages with"
        " coordinates, blocked on the Field Guide terms",
    ),
    where=(
        "https://services3.arcgis.com/3g7oRa9lIIf3eCBb/arcgis/rest/services/OregonHikers_Featured_Hikes_PublicView/FeatureServer/0",
        "https://www.oregonhikers.org/w/api.php",
    ),
    reason="published as hike points, the suggested_hikes type; the Field Guide's trailheads wait on its terms",
)
