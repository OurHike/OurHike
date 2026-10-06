"""National Park Service: suggested hikes, NPS's things to do and tours read here (decision 54 wave 3,
section C, 2026-10-04).

- `nps_things_to_do`: NPS's things to do (`/thingstodo`), read whole, nationally: 3,572 on
  2026-10-04, each with its activities, duration, season, coordinates where it has them, and
  `geometryPoiId`. Not all are hikes: each row's own `activities` say which, and dbt keeps an auto
  tour or a museum visit from becoming a suggested hike.
- `nps_tours`: NPS's tours (`/tours`), read whole, nationally: 717 on 2026-10-04 (both pages, every
  id once), each with its duration range and its ordered stops. Museum walks and drives are tours
  too ('Hiking' is on 220 of the 717), so each tour's own activities and topics say which; and the
  live list holds 2 tours whose `type` is 'Test', which dbt must leave out.

Each list is read by extract/_content.py's NpsContent, NpsAlerts' reader for another endpoint:
NPS_API_KEY from the environment as the gateway's `X-Api-Key` header, never in a URL, and without it
the change check raises Unavailable, so the table is withdrawn and never read as empty
(extract/_json_apis.py, 'THE KEY'). Every run reads the list (the API sends no validators), 500 a
page, stepping by the rows each page returns; the answer's own `total` is the count and the proof,
and a total that moves within one read or a repeated id raises. Rows land as NPS serves them, nested
lists as JSON, except the row's `person_fields`. dbt assigns each club folder its portion by each
row's own park list matched to nps_alerts' `park_codes` map (decision 34); the folders that draw on
these lists hold via notes naming them. The lane is the type's, monthly.

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

National Park Service: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

A point per hike, not a route. `geometryPoiId` joins to the POI layer. Tours include museum walks,
so filter by activity.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): API `/thingstodo?q=hiking`: 1,644 (total 3,572 per c9). Fields
include `duration`, `season`, `petsDescription`, `latitude`/`longitude`, `geometryPoiId`. API
`/tours`: 717 tours with `stops[]` and `durationMin/Max`. The first returned was "Japanese American
Remembrance Trail", 42 stops.

Its `where`: https://mapservices.nps.gov/arcgis/rest/services

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._content import nps_content

CLAIMS = ("nps_things_to_do", "nps_tours")
RESOURCES = [nps_content(key) for key in CLAIMS]
