"""The three layers the job reads, and the fields it asks each one for.

Every URL here was read live by the planning session on 2026-10-24
(apps/remediation/PLAN.md §1 and §2). None of them states a licence: the CSI and
parking layers are ATC's own ArcGIS org, under the maintainer's authorisation
recorded as `atc_licence` in pipeline/sources.json, which PLAN.md §1 says
should be re-read for this app's use rather than assumed to cover it. PAD-US
is a USGS product.
"""

#: ATC's overnight-site inventory: 3,442 rows on 2026-10-24, 2,411 of them
#: user-created. Layer 2 of the same service (`Relative_Site_Density`) carries
#: the same rows and fields, so only layer 1 is read.
CSI_LAYER = "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services/Campsite_Sustainability_Index/FeatureServer/1"

#: Every CSI field the job uses. `Site_Photo_1` is left out on purpose: its
#: links carry access tokens into a storage bucket of ATC's field app, and
#: nobody has said who owns the photos or whether they may be shown
#: (PLAN.md §1), so the job never asks for them.
CSI_FIELDS = (
    "OBJECTID",
    "RIMS_ID",
    "GlobalID",
    "Location",
    "Region",
    "Trail_Club",
    "Longitude",
    "Latitude",
    "AT_Mile_2026",
    "Site_Type",
    "Documented",
    "Inventory_Status",
    "Expansion_Potential_Indicator",
    "Size_ft2",
    "Size_Indicator",
    "Proximity_Other_Site_ft",
    "Proximity_Other_Site_Indicator",
    "Proximity_Water_ft",
    "Nearest_Water_Source",
    "Proximity_Water_Ecological_Indicator",
    "Proximity_Water_Social_Indicator",
    "Proximity_AT_ft",
    "Proximity_AT_Indicator",
    "Median_Percent_Slope_Footprint",
    "Median_Percent_Slope_Buffer",
    "Side_Hill_Footprint_Indicator",
    "Side_Hill_Buffer_Indicator",
    "CSI_Score",
)

#: USGS PAD-US 4.1, one polygon per manager and unit. Queried only around the
#: CSI sites, never downloaded whole.
PADUS_LAYER = "https://services.arcgis.com/v01gqwM5QqNysAAi/ArcGIS/rest/services/Manager_Name_PADUS/FeatureServer/0"
PADUS_FIELDS = ("OBJECTID", "Mang_Name", "Mang_Type", "Des_Tp", "Unit_Nm", "State_Nm", "Own_Name", "Pub_Access", "GAP_Sts")

#: ATC's parking points (483 on 2026-10-24): the "nearest parking" a site page
#: names and the straight-line distance to it.
PARKING_LAYER = "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ANST_Facilities/FeatureServer/2"
PARKING_FIELDS = ("OBJECTID", "Name", "Status")

#: ATC's A.T. centerline (3,028 segments on 2026-10-27), read so a site page can
#: say where to leave the trail and which way to walk (decided 2026-10-26).
#: Simplified on the server to CENTERLINE_SIMPLIFY_DEG, about 5 m, which brought
#: the first 2,000 segments to 1.1 MB (measured 2026-10-27).
CENTERLINE_LAYER = "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ANST_Centerline/FeatureServer/0"
CENTERLINE_SIMPLIFY_DEG = 0.00005

#: Who this job says it is. Its own product token rather than OurHike's
#: `OurHike-pipeline`, because this is not OurHike's pipeline and an operator
#: reading a log should be able to tell the two apart.
PRODUCT_TOKEN = "SiteRemediation"
USER_AGENT = f"{PRODUCT_TOKEN}/0.1 (+https://github.com/OurHike/OurHike/tree/main/apps/remediation)"
