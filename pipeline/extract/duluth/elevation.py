"""City of Duluth Open Data: elevation, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

Not worth loading: the shared USGS elevation source covers it, and 1-ft contours are 12.9 M lines.
It is still a publication, so the dated note must not say "not published".

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Skeptic adds (Measured): "
        "`utility.arcgis.com/usrsvcs/servers/c80f67c16b1d479e991380ca8e447044/rest/services/Elevation/Contours_2021/MapServer`,"
        ' item "Contours_Duluth_2021" (owner `an email address`, modified 2023-09-11): layer 1 "Contour 1 Ft" '
        '12,919,112 lines, layer 2 "Contour 10 Ft" 1,283,094, layer 3 "Contour 50 Ft" 233,674. '
        "`…/2262478d0e3b4c60afdbf8f95b99a398/rest/services/Elevation/Hillshade_DLHBE2021_3xMA_tif/ImageServer`:"
        " a 0.5-unit-pixel hillshade from the 2021 bare-earth survey (modified 2023-02-16). There is an older "
        "`Elevation/Contours_Duluth` too (2021-06-07). Licence: the city's …",
    ),
    where=(
        "https://utility.arcgis.com/usrsvcs/servers/c80f67c16b1d479e991380ca8e447044/rest/services/Elevation/Contours_2021/MapServer",
        "https://utility.arcgis.com/usrsvcs/servers/085f4309eec943a8998e801f7849b1b8/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
