"""National Park Service: challenges, NPS's passport stamp locations read here (decision 54 wave 3,
section C, 2026-10-04).

- `nps_passport_stamp_locations`: NPS's passport stamp locations (`/passportstamplocations`), read
  whole, nationally: 1,093 on 2026-10-04, each a label, a type (visitorcenters and the like) and the
  parks it sits in. No coordinates: a stamp location is placed by its park until a step joins it to
  a POI. The Passport booklet is America's National Parks' (a partner), and the stamp list is NPS's.

Each list is read by extract/_content.py's NpsContent, NpsAlerts' reader for another endpoint:
NPS_API_KEY from the environment as the gateway's `X-Api-Key` header, never in a URL, and without it
the change check raises Unavailable, so the table is withdrawn and never read as empty
(extract/_json_apis.py, 'THE KEY'). Every run reads the list (the API sends no validators), 500 a
page, stepping by the rows each page returns; the answer's own `total` is the count and the proof,
and a total that moves within one read or a repeated id raises. Rows land as NPS serves them, nested
lists as JSON, except the row's `person_fields`. dbt assigns each club folder its portion by each
row's own park list matched to nps_alerts' `park_codes` map (decision 34); the folders that draw on
these lists hold via notes naming them. The lane is the type's, monthly.
"""

from extract._content import nps_content

CLAIMS = ("nps_passport_stamp_locations",)
RESOURCES = [nps_content(key) for key in CLAIMS]
