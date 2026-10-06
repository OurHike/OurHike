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

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

US Fish & Wildlife Service: warnings, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Hunting season is in scope for warnings. The polygons carry no season dates, so they say where
hunting happens, not when. The dates live in the alert blocks above.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `.../FWS_NWRS_HQ_PublicHuntUnits_view/FeatureServer/0`, "FWS
National Hunt Units 2026-2027": 2,215 polygons, with `Huntable`, `Permit_Required`,
`Hunting_Website`. `.../FWS_NWRS_HQ_HuntFishCentroids`: 606 points. Skeptic spot check: still 2,215.
| Skeptic adds: `.../Refuge_Lands_Closed_To_Hunting/FeatureServer/0`, 979 polygons for one refuge
(Edwin B. Forsythe), last edited 2021-07-09. It is local and stale, and is recorded so nobody
mistakes it for a national layer.

Its `where`: https://services.arcgis.com/QVENGdaPbd4LUkLV/arcgis/rest/services https://fws.gov/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
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
