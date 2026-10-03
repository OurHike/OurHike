"""US Fish & Wildlife Service: elevation, published as refuge lidar DEMs and island contours, not
landed.

No raster lands as data (decision 35, pipeline/ELT.md "No raster lands as data"): a DEM, an image
service or a hillshade is read in place or not at all, and USGS 3DEP (_shared/usgs/) is the
elevation source. Contours are vectors, so decision 35 does not cover them, but no mart reads them
and they are background-map material: decision 54's wave 1 registers none, and loading them is the
maintainer's call (decided 2026-10-03).

Licence: the ServCat datasets are federal works (public domain under 17 U.S.C. 105; the catalog's
license field is empty). The contour items' licenseInfo is the FWS liability disclaimer, so
none_stated. The SHARP DEM is an explicit restriction (see below). Value: low. These are per-refuge
2011–2017 …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "re-read 2026-10-03: `Maui_100ft_ElevationContours/FeatureServer/1` 'maucntrs100', 11,457 polylines, "
        "fields FID, CONTOUR and Shape__Length, edited 2021-07-19 (layer 0 does not exist)",
        "data.gov (`catalog.data.gov/search`): at least 7 FWS-published refuge lidar or DEM datasets, each "
        "distributed as zips from `iris.fws.gov/APPS/ServCat/DownloadFile/…`: White River NWR (2017, includes "
        '"WhiteRiver_BE_Raster_DEM32Bit_1M_IMG.zip"), Camas NWR (2 datasets, 2011 and 2013), Hatchie NWR '
        "(2011), Clarks River NWR (2011), Minidoka NWR (2016 bare-earth DEM), Wapato Lake NWR (2011 LAS). Their"
        " `license` field is empty.; FWS AGOL (`orgid:QVENGdaPbd4LUkLV` with lidar, elevation, DEM, contour, "
        'hillshade or terrain: 144 hits): "FWS MB Maui 100 Feet Elevation Contours" (11,457 lines, 2021-07-19 …',
    ),
    where=(
        "https://services.arcgis.com/QVENGdaPbd4LUkLV/arcgis/rest/services/Maui_100ft_ElevationContours/FeatureServer/1",
        "https://data.gov",
        "https://catalog.data.gov/search",
        "https://iris.fws.gov/APPS/ServCat/DownloadFile/",
        "https://fwsprimary.wim.usgs.gov/server/rest/services",
    ),
    reason=(
        "raster and vector contours, not landed: decision 35 lands no raster, and decision 54's wave 1 "
        "registers no contours, which are the maintainer's call; checked gives the measured counts"
    ),
)
