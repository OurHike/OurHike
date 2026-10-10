"""US Fish & Wildlife Service: warnings, 1 ArcGIS layer extracted here (decision 53 phase B,
2026-10-03).

- `fws_hunt_units`: FWS National Wildlife Refuge public hunt units,
  `FWS_NWRS_HQ_PublicHuntUnits_view/FeatureServer/0`. Read monthly, not on the type's lane: standing
  hunt-unit geography with no season dates (dataLastEditDate 2026-09-11), and its 2,215 polygons are
  too large a first read for the hourly lane's 150 s budget. Its row says why phase C should hold it
  back.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://www.fws.gov/refuge/blackwater (html_page).
"""

from extract._kinds import arcgis_layer

CLAIMS = ("fws_hunt_units",)
RESOURCES = [
    arcgis_layer(
        "fws_hunt_units",
        cadence_override="monthly",
        cadence_reason="standing hunt-unit geography with no season dates (dataLastEditDate 2026-09-11), and its 2,215 polygons are too large a first read for the hourly lane's 150 s budget",
    ),
]
