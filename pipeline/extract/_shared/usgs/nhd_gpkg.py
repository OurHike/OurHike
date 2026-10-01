"""The listing of USGS's staged NHD subregion GeoPackages, as `raw_usgs__nhd_hu4_gpkg`: every object, never a zip.

NHD is the retired dataset fetch_trail_water.py derives site water from, as
21 subregion zips of about 270 MB each, which stay files (decision 4). What
lands is the bucket's record of every subregion's zip, `.xml` and `.jpg`, so
a republished subregion shows as a moved ETag. Measured 2026-10-01: 735
objects, 245 of them zips, and none of the corridor's 21 modified since
2024. The 18 objects modified after 2024-06 are all in Great Lakes
subregions the trail does not cross (0405, 0413, 0414, 0427, 0428).

NHD has no sources.json row, which sources.json's own coverage notes record
as a finding: "this is data that ships without being registered". This file
lands the manifest and leaves that registration to its own review.
"""

from extract._kinds import bucket_listing

TYPE = "points_of_interest"
UNREGISTERED = "a non-registry input: lib/nhd.py's NHD_GPKG_URL is its one home, and NHD has no sources.json row"
RESOURCES = [bucket_listing("nhd_hu4_gpkg")]
