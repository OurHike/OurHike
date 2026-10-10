"""The Park Service's trail layers: its national trail layer, and the National Historic Trails' own
alignments and trail lines on NPS's ArcGIS Online organization (NPSAGOL).

`nps_trails` is `NPS_Public_Trails/FeatureServer/0`: 31,484 features on 2026-10-01, against the
registry's 31,485 on 2026-09-30 (coverage audit, batch b6_federal). `max(EDITDATE)` read 2026-09-30, a
real change marker, but the registry row declares no `freshness.field`, so the change check answers
UNKNOWN and the layer is read whole; declaring `freshness.field: EDITDATE` would let unchanged months
skip. `TRLSTATUS` marks 60 rows Temporarily Closed and 20 Decommissioned, and nothing reads it yet
(ORG_COVERAGE_SURVEY.md §3e).

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms. Each is the steward's
dataset, so it is extracted here once, and each NHT club's own trail_lines.py names it (decision 34):

- `nps_oregon_nht`: Oregon National Historic Trail, congressionally designated alignment (NPS). 1 line, keyed on the registry key alone.
- `nps_california_nht`: California National Historic Trail, congressionally designated alignment (NPS). 1 line, keyed on the registry key alone.
- `nps_old_spanish_nht`: Old Spanish National Historic Trail, feasibility study alignment (NPS). 1 line, keyed on the registry key alone.
- `nps_el_camino_tejas_nht`: El Camino Real de los Tejas National Historic Trail, congressionally designated alignment (NPS). 1 line, keyed on the registry key alone.
- `nps_pony_express_nht`: Pony Express National Historic Trail, congressionally designated alignment (NPS). 1 line, keyed on the registry key alone.
- `nps_mormon_pioneer_nht`: Mormon Pioneer National Historic Trail, congressionally designated alignment (NPS). 1 line, keyed on the registry key alone.
- `nps_santa_fe_nht`: Santa Fe National Historic Trail, congressionally designated alignment (NPS). 96 lines, keyed on `GlobalID`.
- `nps_trail_of_tears_nht`: Trail of Tears National Historic Trail, congressionally designated alignment (NPS). 2,006 lines, keyed on `GlobalID`.
- `nps_el_camino_tierra_adentro_nht`: El Camino Real de Tierra Adentro National Historic Trail, congressionally designated alignment (NPS and BLM). 5 lines, keyed on `GlobalID`.
- `nps_butterfield_overland_nht`: Butterfield Overland National Historic Trail, congressionally designated alignment (NPS). 1,748 lines, keyed on `GlobalID`.
- `nps_butterfield_srs_route`: Butterfield Overland Trail Special Resource Study route (NPS). 2 lines, keyed on `GlobalID`.
- `nps_star_spangled_banner_nht`: Star-Spangled Banner National Historic Trail, official driving and water route (NPS). 1 line, keyed on the registry key alone.
- `nps_captain_john_smith_nht`: Captain John Smith Chesapeake National Historic Trail centerline (NPS). 832 lines, keyed on geometry.
- `nps_lewis_clark_nht`: Lewis and Clark National Historic Trail, congressionally designated route (NPS). 62 lines, keyed on geometry.
- `nps_lewis_clark_water_trails`: Lewis and Clark NHT water trails (NPS). 18 lines, keyed on `Trail_Name`.
- `nps_overmountain_victory_nht`: Overmountain Victory National Historic Trail historic route (NPS). 43 lines, keyed on geometry.
- `nps_washington_rochambeau_nht`: Washington-Rochambeau Revolutionary Route NHT driving route centerline (NPS). 11 lines, keyed on `Name`.
- `nps_ala_kahakai_kohala_hema`: Ala Kahakai NHT: Kohala Hema trail (NPS story-map layer). 14 lines, keyed on geometry.
- `nps_ala_kahakai_alanui_aupuni`: Ala Kahakai NHT: Alanui Aupuni trail (NPS story-map layer). 1 line, keyed on the registry key alone.
- `nps_ala_kahakai_kaawaloa`: Ala Kahakai NHT: Ka'awaloa Trail (NPS story-map layer). 1 line, keyed on the registry key alone.
- `nps_ala_kahakai_kiholo_puako`: Ala Kahakai NHT: Kiholo-Puako Trail (NPS story-map layer). 2 lines, keyed on geometry.
- `nps_anza_recreation_trails`: Juan Bautista de Anza NHT recreation trails (NPS-hosted). 578 lines, keyed on `GlobalID`.
- `nps_anza_nht`: Juan Bautista de Anza NHT historic corridor centerline (NPS). 3 lines, keyed on `STATE`.

A designated NHT alignment is a line drawn from planning maps, not a tread: its own licenseInfo says it
'is not a fully developed hiking trail' and must not be shown finer than 1:100,000 (decision 38's
condition). Water trails, driving routes and the Star-Spangled Banner's road and water route are marked
so in their rows' notes.

Not landed, each read 2026-10-03: `LECL_Lewis_and_Clark_NHT_Auto_Route_Final_Combined` (3,396 road
segments) and `JUBA_AutoTourRoute` (1,084) are driving routes on roads;
`POEX_Pony_Express_ReRide_Route_2026_Layer_View` (5,290 road segments) is a 2026 horseback event's road
route; `Lewis_and_Clark_Trail_Historic_Route` (57) is an archive whose own description says the
designated route above 'should be used in place of this dataset'; and
`Ala_Kahakai_National_Historic_Trail_Official_Corridor` is a corridor polygon, not a line. The SAME_AS
notes below are views or twins of two of the registered layers.
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = (
    "nps_trails",
    "nps_oregon_nht",
    "nps_california_nht",
    "nps_old_spanish_nht",
    "nps_el_camino_tejas_nht",
    "nps_pony_express_nht",
    "nps_mormon_pioneer_nht",
    "nps_santa_fe_nht",
    "nps_trail_of_tears_nht",
    "nps_el_camino_tierra_adentro_nht",
    "nps_butterfield_overland_nht",
    "nps_butterfield_srs_route",
    "nps_star_spangled_banner_nht",
    "nps_captain_john_smith_nht",
    "nps_lewis_clark_nht",
    "nps_lewis_clark_water_trails",
    "nps_overmountain_victory_nht",
    "nps_washington_rochambeau_nht",
    "nps_ala_kahakai_kohala_hema",
    "nps_ala_kahakai_alanui_aupuni",
    "nps_ala_kahakai_kaawaloa",
    "nps_ala_kahakai_kiholo_puako",
    "nps_anza_recreation_trails",
    "nps_anza_nht",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]

SAME_AS = (
    SameAs(
        original="nps_anza_recreation_trails",
        copy=(
            "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/JUBA_NHT_RECREATION_TRAILS_view/FeatureServer/0",
        ),
        confirmed=date(2026, 10, 3),
        checked=(
            "An ArcGIS Online view (isView true) of JUBA_NHT_RECREATION_TRAILS: its 422 GlobalIDs are all "
            "among the original's 578 (compared 2026-10-03), the same 87 fields, the same dataLastEditDate "
            "2026-08-11",
        ),
    ),
    SameAs(
        original="nps_anza_nht",
        copy=("https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/JUBA_HistoricTrail_ln/FeatureServer/0",),
        confirmed=date(2026, 10, 3),
        checked=(
            "The same 3 rows attribute for attribute as JUBA_NHT_ (compared 2026-10-03, row ids aside), the "
            "same statistics (count 3, max(FID) 3, sum(Shape_Leng) 21.40), the same description, published 25"
            " minutes apart on 2025-08-18",
        ),
    ),
)
