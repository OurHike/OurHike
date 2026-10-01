"""US Fish & Wildlife Service: elevation, published, and not landed (coverage audit 2026-10-01, batch
p07_persist).

Licence: the ServCat datasets are federal works (public domain under 17 U.S.C. 105; the catalog's
license field is empty). The contour items' licenseInfo is the FWS liability disclaimer, so
none_stated. The SHARP DEM is an explicit restriction (see below). Value: low. These are per-refuge
2011–2017 …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "data.gov (`catalog.data.gov/search`): at least 7 FWS-published refuge lidar or DEM datasets, each "
        "distributed as zips from `iris.fws.gov/APPS/ServCat/DownloadFile/…`: White River NWR (2017, includes "
        '"WhiteRiver_BE_Raster_DEM32Bit_1M_IMG.zip"), Camas NWR (2 datasets, 2011 and 2013), Hatchie NWR '
        "(2011), Clarks River NWR (2011), Minidoka NWR (2016 bare-earth DEM), Wapato Lake NWR (2011 LAS). Their"
        " `license` field is empty.; FWS AGOL (`orgid:QVENGdaPbd4LUkLV` with lidar, elevation, DEM, contour, "
        'hillshade or terrain: 144 hits): "FWS MB Maui 100 Feet Elevation Contours" (11,457 lines, 2021-07-19 …',
    ),
    where=(
        "https://data.gov",
        "https://catalog.data.gov/search",
        "https://iris.fws.gov/APPS/ServCat/DownloadFile/",
        "https://fwsprimary.wim.usgs.gov/server/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
