"""Where USGS stages the National Hydrography Dataset's subregion GeoPackages.

Two readers share this: `fetch_trail_water.py`, which downloads the
corridor's 21 subregions, and `extract/_shared/usgs/nhd_gpkg.py`, which lands
the bucket's listing for them (#1793 — Rebuild the data platform as dlt →
dbt: seven contracted marts, a monthly refresh, published docs, and lighter
phone downloads). It lives here, apart from the fetcher, because the fetcher
imports pmtiles and the geometry stack, and the extract job installs neither
(`requirements-extract.in`).
"""

from __future__ import annotations

NHD_GPKG_URL = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/NHD/HU4/GPKG/NHD_H_{huc4}_HU4_GPKG.zip"
