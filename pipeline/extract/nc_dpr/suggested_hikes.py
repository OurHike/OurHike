"""NC Division of Parks and Recreation: suggested hikes, its parks' trail tables read here (decision 54 wave 5,
section K, 2026-10-04).

- `nc_parks_trails`: ncparks.gov/state-parks and each park's /trails page, 42 pages and 407 trails, each its name,
  blaze, length, difficulty, use and whether it is accessible, in the park the page names. The /trails URL is built
  from each park's link; four parks answer 404 for it and have no row.

The reader is extract/_pages_content.py's ContentPages with the `nc_parks_trails` site parser: the rows hashed for
the change check (no page validator decides FRESH), facts and the link only, never the club's own wording. Its row
in sources.json holds the terms as found, the live read and the measured key, the trails page and the trail's name.
The terms are nc.gov's, quoted on the row: permission to copy for non-commercial use, without alteration and citing
the source, which restricts reuse and refuses nothing.

The state trails pages the coverage audit also names (trails.nc.gov/state-trails/<trail>, 15) and the `WEBLINK`
field on `State_Trails` are not read here.

The note this replaces read, whole:

NC Division of Parks & Recreation — NC Trails: suggested hikes, published, and not landed (coverage
audit 2026-10-01, batch c9_federal_state_rest).

Page.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `ncparks.gov/state-parks/<park>/trails` pages;
`trails.nc.gov/state-trails/<trail>` (15 trail pages); the `WEBLINK` field on `State_Trails`.

Its `where`: https://ncparks.gov/state-parks/ https://trails.nc.gov/state-trails/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pages_content import content_pages

CLAIMS = ("nc_parks_trails",)
RESOURCES = [content_pages("nc_parks_trails")]
