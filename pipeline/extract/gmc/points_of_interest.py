"""GMC's five MASTER point layers for the Long Trail: overnight sites, parking, privies, vistas and summits, map features.

Read live 2026-10-03 for decision 54's wave 1. Each row lists the person fields it never asks for
(SOURCE and LastEdBy hold surveyors' and editors' names). ATC's facility layers already hold GMC's
A.T. sites (code 4): independent data of the same ground, deduplicated in dbt (decision 34).
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "gmc_overnight_sites",
    "gmc_parking",
    "gmc_privies",
    "gmc_viewpoints",
    "gmc_map_features",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
