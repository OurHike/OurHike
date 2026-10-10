"""AMC's own point layers: White Mountain lodging, destinations, eastern Pennsylvania trailheads, and the New England Trail's Connecticut points and parking.

Read live 2026-10-03 for decision 54's wave 1. amc_at/ draws from amc_destinations here rather than
extracting it twice (decision 34). AMC's org lists 380 services; only these five were read.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "amc_lodging",
    "amc_destinations",
    "amc_trailheads_and_parking",
    "amc_net_points_of_interest",
    "amc_net_parking",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
