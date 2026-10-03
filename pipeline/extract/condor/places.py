"""Condor Trail Association: places, drawn from usfs/'s resources, and the rest not landed (decision 54,
wave 1, read 2026-10-03).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via usfs `usfs_forest_boundaries` (forestorgcode '0507', Los Padres) and `usfs_wilderness_areas` (Sespe, "
        "Matilija, Dick Smith, San Rafael and the rest), registered 2026-10-03.",
        "Not landed: the Sespe Condor Sanctuary polygon, which exists only in an advocacy NGO's item "
        "(Sespe_Condor_Sanctuary/FeatureServer); it is third-party and no folder holds its steward.",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_ForestSystemBoundaries_01/MapServer/0",
        "https://services9.arcgis.com/olCAyDMW794Lg7Au/arcgis/rest/services/Sespe_Condor_Sanctuary/FeatureServer",
    ),
    reason="partly drawn from usfs/'s resources (decision 34); the Sespe Condor Sanctuary polygon is not landed",
)
