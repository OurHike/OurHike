"""Palmetto Conservation Foundation: suggested hikes, the Palmetto Trail's 33 passages, from the table
palmetto/points_of_interest.py extracts as `palmetto_trail_passages` (decision 54 wave 5, section K, 2026-10-04).

THE LEAD'S RULING, 2026-10-04: "(a), one reader of the 33 passage pages." Section S's reader fetches each passage
page for its map's markers and line, and section K's read the same pages again for the fact grid; decision 34 lands
an upstream once. So extract/_pages_points.py's parse_palmetto_passage reads the grid in the same fetch and writes
each page's facts on every row it lands for that page: length_text and length_miles (where the text states one
figure), difficulty, region, surface, pets, fees, camping and hunting_grounds, first lines only, never the
foundation's explanation under them nor the description. A page always lands its line's row, so the one passage
whose map plots no marker (henry-trail, the live read of 2026-10-04, 20:42 to 20:44Z) keeps its facts.

This file SHARES that resource: one raw table, staged once. pipeline/make_dbt_staging.py stages it into
int_suggested_hikes__club_unioned as one row per page (`source_url`) from the fields palmetto_trail_passages' row
names in `shared_page_rows`: the passage's name, its length as text and in miles, the page and its region. The
section K row `palmetto_passages`, which read the pages a second time, is withdrawn.

The note this replaces read, whole:

Palmetto Conservation Foundation: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

Pages.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): 33 passage pages: length, difficulty, activities and description.

Its `where`: https://palmettoconservation.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

SHARES = "points_of_interest"
