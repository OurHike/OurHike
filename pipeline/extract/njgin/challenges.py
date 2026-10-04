"""NJ DEP (NJGIN's folder): challenges, the Celebrate 250 Challenge, behind the host's wall, and not landed
(decision 54 wave 5, section K, 2026-10-04).

dep.nj.gov is behind Incapsula's challenge (the coverage audit read the page's search-index summary only: a 2026
yearlong challenge, up to 'hiking 25 different trails in a year', a $7 passport book stamped at staffed sites).
Nothing past the wall is read. No request sent today.

The note this replaces read, whole:

NJDEP / NJGIN — Statewide Trails: challenges, published, and not landed (coverage audit 2026-10-01,
batch b5_nyc_nj_ct_ma_pa).

The passport of stamped sites fits #1780 — Let a club publish a challenge — places on its own trails
that hikers opt into and tag at camp — starting with the ATC's A.T. Summer Bucket List's model (now on
main via #1798 — Challenges: a club's list of places on its own trails, joined and tagged at …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): "Celebrate 250 Challenge",
`https://dep.nj.gov/parksandforests/get-outside/celebrate-250-challenge/`. The search-index summary says
it is a 2026 yearlong challenge, with options up to "hiking 25 different trails in a year" and 250
miles, a $7 NJ State Parks passport book stamped per staffed site, and a certificate. The page itself is
Incapsula-walled. Also the StoryMap "New Jersey Publicly Accessible High Points By County"
(`cec918caa77f45ad92e18accc64c57eb`, 2025-04-17), backed by the 21-point layer above.

Its `where`: https://dep.nj.gov/parksandforests/get-outside/celebrate-250-challenge/
https://mapsdep.nj.gov/arcgis/rest/services
https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/arcgis/rest/services

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) dep.nj.gov answered with Incapsula's challenge",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://dep.nj.gov/parksandforests/get-outside/celebrate-250-challenge/",),
    reason="behind a wall (Incapsula), not solved",
)
