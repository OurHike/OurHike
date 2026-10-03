"""Colorado Parks & Wildlife — COTREX: photos, could not be told (coverage audit 2026-10-01, batch
b7_long_trails_states).

Still UNKNOWN. ArcGIS is exhausted. CPW's own media library or Flickr account was not found: guessed
Flickr slugs 404, and a web search did not name one.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`CPW Facilities.PHOTO` exists; I did not sample its values or licence. The COTREX terms license user "
        "content to CPW only.",
        "Skeptic adds (Measured): `PHOTO` is filled on 31 of 5,520 facilities, with internal file names and "
        "paths (`yam001Fa`, `L:\\parks\\work\\stg\\themes\\infrastr\\fldpics\\STG001F.tif`), not URLs, so it serves no"
        ' photo. `PhotoPoints/FeatureServer/1` "Photo Monitoring Point": 74 forestry photo-monitoring plots '
        "(2023-03-21), with no licence. A keyword scan of all 821 org items found no other photo collection.",
    ),
    where=(
        "https://services5.arcgis.com/ttNGmDvKQA7oeDQ3/arcgis/rest/services/PhotoPoints/FeatureServer/1",
        "https://services3.arcgis.com/0jWpHMuhmHsukKE3/arcgis/rest/services",
        "https://trails.colorado.gov/",
    ),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
