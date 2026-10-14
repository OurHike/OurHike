"""Florida State Parks (Florida DEP's Division of Recreation and Parks): closures, and the park boundaries that place them.

Its trail_orgs.json row, `fl-state-parks` (`load: ship`), was approved on 2026-10-11 (decision 121, review page 01), so
this file moved here from _shared/fl_state_parks/, where decision 122 had loaded it held, and every raw table kept its
name. The coverage audit's fl-state-parks-fkoht folds into this folder (the Florida Keys Overseas Heritage Trail is a
state park).

- `fl_state_parks_day_use_status`: `Florida_State_Parks_Operational_Status/FeatureServer/6`, each park's status
  (176; 35 closed for a hurricane or tropical storm on 2026-10-09, 12 at 18:52 UTC on 2026-10-11).
- `fl_state_parks_campground_status`: `.../FeatureServer/5`, each campground's status (184 rows, 120 of them
  parks with no campground).
- `fl_state_parks_park_boundaries`: FDEP's `OpenData/PARKS_BOUNDARIES/MapServer/0` on ca.dep.state.fl.us, each park's
  own boundary (179 polygons, read 2026-10-11). Not a notice: the place of one.

A CLOSED PARK CLOSES ITS TRAILS, AND ITS PLACE IS ITS OWN BOUNDARY. The maintainer chose what a park closed for a storm
does (the poll of 2026-10-11, review page 01, P5, frame A, decision 168): it closes the trails inside it until the park's
own status reopens it, so every Closed-<reason> status reads as closing the trail, by the shared word 'closed'
(seeds/notice_words.csv, decision 190; the campground layer's Closed values read the same way since, its rows naming
the park and no campground). The
status layer is points with no park id, so a closed park sat at its point, and a planned hike's list showed it only to
a route passing within client/src/lib/plannedNotices.ts's NOTICE_REACH_FEET (300) of that point. The same poll's Q3
("Its own boundary", decision 185) places it by FDEP's own park boundaries instead, as a general rule and not one for
Florida: a status point inside exactly one of its steward's own areas takes that area as its place
(seeds/notice_steward_areas.csv; int_closures__club_notices' rule 4), and one inside none or several keeps its point.
At 18:52 UTC on 2026-10-11, 173 of the 176 points lay inside exactly one boundary, each the boundary of the point's own
SITE_NAME, and 3 inside none (fl_state_parks_park_boundaries' sources.json notes name them). The trails a closed park
closes are then the ones inside its boundary. A campground's status is about the campground and not the park around
it, so the campground layer has no seed row and keeps its own points.

THE BOUNDARIES RIDE THE NOTICES JOB, DAILY. The build that places the status points is the hourly one, and its
warehouse holds a conditions leg's tables and a notices leg's served copy, never the monthly store
(publish-conditions.yml), so a monthly `places.py` resource would never reach it: tests/test_generated_notice_models.py
holds that, for every steward's areas layer as for every notice source. As a resource of this file its type is
closures, whose lane is the hourly one, and extract/_run.py's job_of() gives it to the notices job.
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

STATUS = ("fl_state_parks_day_use_status", "fl_state_parks_campground_status")
BOUNDARIES = "fl_state_parks_park_boundaries"
CLAIMS = (*STATUS, BOUNDARIES)
RESOURCES = [arcgis_layer(key) for key in STATUS] + [
    arcgis_layer(
        BOUNDARIES,
        cadence_override="daily",
        cadence_reason=(
            "Daily, not every notices run: the layer has no editor tracking and no date field, so its change check "
            "answers UNKNOWN and every read is a whole one (1,147,902 vertices, 47,598,120 bytes of GeoJSON, read "
            "2026-10-11), of outlines its own description dates 'as of September 1st, 2017' and its item 'as of "
            "January 27, 2026'. A daily resource still rides the hourly lane (extract/_run.py's DUE_AFTER), so the "
            "notices job reads it and the hourly build that places the status points holds it. @unvalidated as the "
            "right interval: how often FDEP redraws a boundary, which no read here has seen, would settle it"
        ),
    )
]
SAME_AS = (
    SameAs(
        original=BOUNDARIES,
        copy=(
            "https://services1.arcgis.com/nRHtyn3uE1kyzoYc/arcgis/rest/services/Florida_State_Park_Boundaries_SNAPP/FeatureServer/0",
            "b3c4cbd990c74f34ba322158c47f24c5",
        ),
        confirmed=date(2026, 10, 11),
        checked=(
            "FLPARKSGIS's hosted 'Florida State Park Boundaries (SNAPP)' (item b3c4cbd990c74f34ba322158c47f24c5, created "
            "2026-09-22, data last edited the same day) against PARKS_BOUNDARIES/MapServer/0, both read 2026-10-11: "
            "179 features in each, the same 179 SITE_NAME values, sum(ACREAGE) 821,584.66 and sum(UPLAND) 685,074.72 "
            "in each, the same fields under shapefile names (ABBREVIATI, SHAPE_Leng), and the description and licence "
            "words of the item that registers the MapServer layer",
        ),
    ),
)
