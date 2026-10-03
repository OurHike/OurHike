"""Colorado Parks & Wildlife — COTREX: elevation, published only as rasters, not landed.

No raster lands as data (decision 35, pipeline/ELT.md "No raster lands as data"): a DEM, an image
service or a hillshade is read in place or not at all, and USGS 3DEP (_shared/usgs/) is the
elevation source.

Licences: NDIS copyrightText empty, none_stated. OIT on AWS: "License:
https://creativecommons.org/publicdomain/zero/1.0/legalcode", open_licence CC0 1.0, a state work.
The OIT item's licenseInfo is a disclaimer ("The State of Colorado makes no representations or
warranty as to the completeness, accuracy…"). The CWCB portal states no licence; Boulder County's
link item to it says CC BY 4.0, secondhand. Folders: a `_shared/` Colorado OIT folder (name
Reasoned), and `_shared/usgs` for the 1 m 3DEP mirror. NDIS could go to `cpw/` if CPW confirms the
raster is theirs (@unvalidated; CPW or NDIS staff would settle it). 3DEP remains the profile source;
whether any of these beats it is unmeasured.

Restated in full from the persistence pass's batch file; reference/org_coverage.json keeps a trimmed
copy.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "re-read 2026-10-03: NDIS `Elevation/MapServer` still holds one layer, 'Elevation', a Raster Layer "
        "(capabilities Map, Query and Data)",
        "(1) NDIS, `https://ndismaps.nrel.colostate.edu/arcgis/rest/services` (30 services walked; folders "
        "include `CPW`, `HuntingAtlas2025` and `FishingAtlas2025`), has `Elevation/MapServer`: one Raster "
        "Layer, capabilities Map, Query and Data, extent Colorado in UTM 13N. An identify at Mount Elbert's "
        "summit coordinates returned `Pixel Value` 14423; the published summit elevation is 14,440 ft, so the "
        "unit is feet (Reasoned from one point). CPW's AGOL org `ttNGmDvKQA7oeDQ3`: lidar 0, contour 0, terrain"
        ' 0. Its "Colorado Elevation Above Below 7000 feet" (`e26412bafe4b463cab06d9b737bd416f`) is a two-class'
        ' reclassification of "the 10 meter DEM for Colorado". The registered endpoint\'s org, '
        "`0jWpHMuhmHsukKE3`, is Boulder County's, not CPW's; its hillshade ImageServer and 2/10/20/40 ft "
        'contour services are county-only. (3) State: Colorado OIT\'s "1-meter DEM" '
        "(`0348f239acf0422fb9cda3338ee38b9c`, a tiles-only MapServer at `ti-cooit.img.arcgis.com`) links to "
        "`https://registry.opendata.aws/colorado-elevation-data/`. That registry entry describes the bucket "
        "`colorado-public-elevation-data` (us-west-2), whose top-level prefixes are `2015/`, `2016/`, `2018/`, "
        "`2019/`, `2021/`, `DEM/DEM.tiles/`, `contours/Contours.vtiles/` and `USGS_one_meter_dem/` (more than "
        '1,000 GeoTIFF objects, a 3DEP mirror). CWCB\'s "CO Hazard Mapping & Risk MAP Portal" serves '
        "`https://coloradohazardmapping.com/api/lidar/datasets` (JSON): 62 lidar collections, 2011–2020, as DEM"
        ' (TIF, IMG, ADF, ASC) and LAS. data.colorado.gov (Socrata) "Contour Lines in Colorado" (`sc9q-ryk8`) '
        "links to USGS `edcftp`, attribution USGS, public domain, contours last entered 2009. (5) data.gov "
        '"Colorado lidar elevation": USGS research DEMs only. The COTREX app\'s own elevation profiles were not '
        'inspected: its terms forbid "any means other than the currently available interfaces".',
    ),
    where=(
        "https://ndismaps.nrel.colostate.edu/arcgis/rest/services",
        "https://registry.opendata.aws/colorado-elevation-data/",
        "https://coloradohazardmapping.com/api/lidar/datasets",
        "https://creativecommons.org/publicdomain/zero/1.0/legalcode",
        "https://ndismaps.nrel.colostate.edu/arcgis/rest/services/Elevation/MapServer",
        "https://ti-cooit.img.arcgis.com",
        "https://data.colorado.gov",
        "https://data.gov",
        "https://services3.arcgis.com/0jWpHMuhmHsukKE3/arcgis/rest/services",
    ),
    reason="raster, not landed: decision 35 lands no raster as data, and 3DEP (_shared/usgs/) is the elevation source",
)
