"""PASDA / PA DCNR: warnings, from DCNR's ParkAdvisory API, hourly (decision 53, phase B).

`pa_dcnr_park_advisories` reads each park id sources.json's entry lists in
`park_ids`: Laurel Ridge State Park (6219), which administers the Laurel
Highlands Hiking Trail, and Tioga State Forest (8116). An advisory is HTML
text with an IsAlert flag and nothing else, so each row is keyed by a hash of
its park and text (extract/_json_apis.py's advisory_key).

WHY THIS FOLDER AND NOT laurel/. The API is PA DCNR's own, it answers for
every park and forest DCNR runs, and one upstream is extracted once, in its
steward's folder (decision 34). trail_orgs.json names this folder's org
"PASDA / PA DCNR" and points laurel's row here (`via: pasda`), and
laurel/trail_lines.py already draws from this folder, so laurel's closures.py
and warnings.py are `via` notes naming this file, and another club's park is
a new id on the same entry rather than a second resource.

LIVE, 2026-10-03: Laurel Ridge's answer carries IsAlert true, "The unnamed
tributary between mile-marker 24 and 25 has been contaminated by lead and
other heavy metals. Please do not use this as a drinking water source." That
is a water fact at an LHHT mile and belongs on the water path as well as in
warnings; nothing reads it there yet.

WHAT THIS MISSES: Tioga's answer held only two statewide items (drones,
firewood) and not the Asaph Run reroute its advisories page carries (the
decision 53 inventory, 2026-10-03), so for a state forest the page, not this
API, is the channel.

The coverage audit's other DCNR warnings (2026-10-01), all ArcGIS and all
decision 54 wave 1's once registered: `agsprod/BOF/HuntStateForest/MapServer`
(11 hunting layers), `pasda/DCNR2/MapServer/9` ("State Forest Gated Roads
Open for Deer Season 202310", 308 features) and `BOF/SpongyMothSprayBlocks`.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check):
https://www.pa.gov/agencies/dcnr/recreation/where-to-go/state-forests/find-a-forest/tioga/advisories
(html_page), the channel WHAT THIS MISSES names.

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://maps.dcnr.pa.gov/agsprod/rest/services/BOF/HuntStateForest/MapServer, 11 layers ('Roads
Opened for Deer Season', 'Elk Hunt Zones'); no layer was read, so none can be registered yet;
https://maps.dcnr.pa.gov/agsprod/rest/services/BOF/SpongyMothSprayBlocks/MapServer, one layer
'Spongy Moth Spray Blocks', not read;
https://mapservices.pasda.psu.edu/server/rest/services/pasda/DCNR2/MapServer/9, 'Gated Roads Open
for Deer Season 202310', the 2023 season's roads; self-expiring and three seasons old.
"""

from extract._json_apis import dcnr_park_advisories

CLAIMS = ("pa_dcnr_park_advisories",)
RESOURCES = [dcnr_park_advisories("pa_dcnr_park_advisories")]
