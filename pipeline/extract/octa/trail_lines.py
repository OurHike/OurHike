"""Oregon-California Trails Association: the emigrant trails' traces OCTA maps in the field, from its own
ArcGIS Online organization.

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms.

- `octa_hastings_cutoff_route`: Hastings Cutoff route, OCTA map (OCTA). 375 lines, keyed on `ident`.
- `octa_naches_pass_trail`: Naches Pass Trail, 2020 mapping (OCTA). 83 lines, keyed on `Name`.
- `octa_natcon_boardman_tracks_2016`: Boardman tracks, 2016 (OCTA). 7 lines, keyed on `Name`.
- `octa_corral_springs_tracks_2015`: Corral Springs tracks, 2015 (OCTA). 2 lines, keyed on `Name`.
- `octa_whitman_longsegs_2020`: Whitman Mission route long segments, 2020 (OCTA). 15 lines, keyed on `Name`.
- `octa_polylines_oregon_trail_kml`: Oregon Trail polylines from KML (OCTA). 2 lines, keyed on `Name`.
- `octa_lockhart_trail_route`: Lockhart Trail route from paper maps (OCTA). 5 lines, keyed on geometry.
- `octa_barlow_road_62`: Barlow Road, atlas page 62 (OCTA). 1 line, keyed on the registry key alone.
- `octa_barlow_road_63`: Barlow Road, atlas page 63 (OCTA). 1 line, keyed on the registry key alone.
- `octa_barlow_road_64`: Barlow Road, atlas page 64 (OCTA). 6 lines, keyed on geometry.
- `octa_barlow_road_65`: Barlow Road, atlas page 65 (OCTA). 4 lines, keyed on geometry.
- `octa_barlow_road_86`: Barlow Road, atlas page 86 (OCTA). 2 lines, keyed on `InLine_FID`.
- `octa_molalla_young_trail_62`: Molalla/Young Trail, atlas page 62 (OCTA). 1 line, keyed on the registry key alone.
- `octa_molalla_young_trail_63`: Molalla/Young Trail, atlas page 63 (OCTA). 1 line, keyed on the registry key alone.
- `octa_klamath_fremont_trail_65`: Klamath/Fremont Trail, atlas page 65 (OCTA). 1 line, keyed on the registry key alone.
- `octa_klamath_fremont_trail_71`: Klamath/Fremont Trail, atlas page 71 (OCTA). 1 line, keyed on the registry key alone.
- `octa_meek_trail_65`: Meek Trail, atlas page 65 (OCTA). 1 line, keyed on the registry key alone.
- `octa_meek_trail_71`: Meek Trail, atlas page 71 (OCTA). 1 line, keyed on the registry key alone.
- `octa_meek_trail_86`: Meek Trail, atlas page 86 (OCTA). 1 line, keyed on the registry key alone.
- `octa_oregon_trail_71`: Oregon Trail, atlas page 71 (OCTA). 4 lines, keyed on geometry.
- `octa_oregon_trail_81`: Oregon Trail, atlas page 81 (OCTA). 2 lines, keyed on `InLine_FID`.
- `octa_oregon_trail_85`: Oregon Trail, atlas page 85 (OCTA). 1 line, keyed on the registry key alone.
- `octa_oregon_trail_86`: Oregon Trail, atlas page 86 (OCTA). 10 lines, keyed on geometry.
- `octa_oregon_trail_87`: Oregon Trail, atlas page 87 (OCTA). 1 line, keyed on the registry key alone.
- `octa_oregon_trail_88`: Oregon Trail, atlas page 88 (OCTA). 1 line, keyed on the registry key alone.
- `octa_oregon_trail_89`: Oregon Trail, atlas page 89 (OCTA). 1 line, keyed on the registry key alone.
- `octa_bonneville_trail_1834_86`: Bonneville Trail of 1834, atlas page 86 (OCTA). 1 line, keyed on the registry key alone.

Every line here is a trace of a historic route, not a maintained tread (coverage audit, finding 2).
NPS's designated alignments of the Oregon and California NHTs are nps/'s. Not landed, read 2026-10-03:
`Feasibility_Study_Trail_for_Congress_Map` (27 line layers) and `Other_Feasibility_Study_Trails_WFL1`
(84 line layers, 42 of them `_SimplifyLine` copies of the other 42), routes proposed to Congress in a
feasibility study rather than mapped traces; `CALTRANS_McCloud_Project` and
`Gateway_West_Transmission_Line`, a highway and a power line; and `High_Potential_Sites`, points.
`20150609_OREG_OR_Welch` is an Oregon clip of NPS's alignment (SAME_AS below).
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = (
    "octa_hastings_cutoff_route",
    "octa_naches_pass_trail",
    "octa_natcon_boardman_tracks_2016",
    "octa_corral_springs_tracks_2015",
    "octa_whitman_longsegs_2020",
    "octa_polylines_oregon_trail_kml",
    "octa_lockhart_trail_route",
    "octa_barlow_road_62",
    "octa_barlow_road_63",
    "octa_barlow_road_64",
    "octa_barlow_road_65",
    "octa_barlow_road_86",
    "octa_molalla_young_trail_62",
    "octa_molalla_young_trail_63",
    "octa_klamath_fremont_trail_65",
    "octa_klamath_fremont_trail_71",
    "octa_meek_trail_65",
    "octa_meek_trail_71",
    "octa_meek_trail_86",
    "octa_oregon_trail_71",
    "octa_oregon_trail_81",
    "octa_oregon_trail_85",
    "octa_oregon_trail_86",
    "octa_oregon_trail_87",
    "octa_oregon_trail_88",
    "octa_oregon_trail_89",
    "octa_bonneville_trail_1834_86",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]

SAME_AS = (
    SameAs(
        original="nps_oregon_nht",
        copy=("https://services6.arcgis.com/RyWFDAB3oVbYYzSx/arcgis/rest/services/20150609_OREG_OR_Welch/FeatureServer/0",),
        confirmed=date(2026, 10, 3),
        checked=(
            "Its item is titled 'OT 100K NPS 20150609', its one line has OREG_NHT's own fields (Id, "
            "DateSent), and its extent ends where NPS's does, at lon -122.79 and lat 45.74, inside NPS's "
            "line's: an Oregon clip of the 1:100,000 alignment (compared 2026-10-03)",
        ),
    ),
)
