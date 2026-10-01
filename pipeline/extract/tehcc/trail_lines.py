"""Tennessee Eastman Hiking & Canoeing Club: trail lines, drawn from another folder's resource
(coverage audit 2026-10-01, batch c3_at_clubs_south).

The non-A.T. lines are new to the project. Where they overlap state or USFS rows, this is the
dual-source case #1709 — Register the steward and the redistributor both, and declare which one wins
where they overlap exists for.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`centerline` (191 features, 132.1 mi under `TEHCC`, plus 1.1 mi under `"26"`) and `side_trails` (69). '
        "TEHCC's own geometry: the wiki `GeoJson:` namespace (ns 420), 156 FeatureCollection pages. 7 are A.T. "
        "sections, such as `GeoJson:Carver's Gap to US19E` (a LineString, Z = 0, edited 2026-07-28, 72,638 "
        "bytes). The rest are local trails in TN, VA and NC (Bays Mountain Park, Roan Mountain SP, Laurel Fork "
        "and others). Read through `api.php?action=query&prop=revisions&rvslots=main`. "
        "`clubwiki/kml/TEHCC_AT.kml` (478 bytes) is only a NetworkLink to a legacy Google My Maps URL.",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://tehcc.org/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
