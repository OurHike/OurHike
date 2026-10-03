"""Appalachian Mountain Club (A.T. sections): points of interest, drawn from amc/'s and atc/'s resources.

ATC's facility layers hold the A.T. sites AMC maintains (code 1): shelters 19, the 8 huts among them,
campsites 18, privies 20, parking 9, viewpoints 126. AMC's off-A.T. destinations are amc_destinations,
extracted once in amc/points_of_interest.py (decision 34).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "AMC_Destinations/FeatureServer/0, 61 points (Tentsite - Primitive Camp 14, Shelter 12, Cabin Self "
        "Service 8, White Mountain Hut 8 and others; read 2026-10-03), registered as amc_destinations and "
        "extracted in amc/",
        "ATC's shelters, campsites, privies, parking and viewpoints layers, which hold the A.T. sites AMC "
        "maintains (code 1), extracted in atc/",
    ),
    where=(
        "https://services9.arcgis.com/mxpFc8oFRyNIV03y/arcgis/rest/services/AMC_Destinations/FeatureServer/0",
        "https://www.outdoors.org/",
    ),
    reason=(
        "drawn from amc/'s and atc/'s resources, extracted once there (decision 34); checked names the layers"
        " this org's data arrives in"
    ),
)
