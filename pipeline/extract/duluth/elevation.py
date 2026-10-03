"""City of Duluth Open Data: elevation, published as vector contours and a hillshade, not landed.

No raster lands as data (decision 35, pipeline/ELT.md "No raster lands as data"): a DEM, an image
service or a hillshade is read in place or not at all, and USGS 3DEP (_shared/usgs/) is the
elevation source. Contours are vectors, so decision 35 does not cover them, but no mart reads them
and they are background-map material: decision 54's wave 1 registers none, and loading them is the
maintainer's call (decided 2026-10-03). Duluth's 2021 contours are 14,435,880 lines across three
layers (re-counted 2026-10-03).

Not worth loading: the shared USGS elevation source covers it, and 1-ft contours are 12.9 M lines.
It is still a publication, so the dated note must not say "not published".

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "re-counted 2026-10-03 (returnCountOnly) on `Elevation/Contours_2021/MapServer`: layer 1 'Contour 1 "
        "Ft (Scale < 5000)' 12,919,112 polylines, layer 2 'Contour 10 Ft (Scale 5000-24000)' 1,283,094, "
        "layer 3 'Contour 50 Ft (Scale > 24000)' 233,674; none has editingInfo",
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
    reason=(
        "raster and vector contours, not landed: decision 35 lands no raster, and decision 54's wave 1 "
        "registers no contours, which are the maintainer's call; checked gives the measured counts"
    ),
)
