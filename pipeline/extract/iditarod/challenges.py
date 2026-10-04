"""Iditarod Historic Trail Alliance: challenges, the passport stamps, whose locations the page does not list,
and not landed (decision 54 wave 5, section K, 2026-10-04).

/passport-stamp-program.html says the Iditarod NHT has 'a total of 9 stamps at different locations' and lists none;
the coverage audit places the list on page 14 of the Visitor Guide PDF, a magazine layout (suggested_hikes.py).

The note this replaces read, whole:

Iditarod Historic Trail Alliance: challenges, published, and not landed (coverage audit 2026-10-01,
batch c11_nht).

A ready-made #1780 candidate once the 9 locations are geocoded

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `passport-stamp-program.html`: "a total of 9 stamps at different
locations along the trail" (page; list in Visitor Guide p.14). BLM page
`blm.gov/documents/alaska/public-room/educational-material/iditarod-national-historic-trail-passport-program`.
"Junior Trailblazer" page

Its `where`:
https://blm.gov/documents/alaska/public-room/educational-material/iditarod-national-historic-trail-passport-program

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://www.iditarod100.org/passport-stamp-program.html (HTTP 200, 84,171 bytes, 2026-10-04): '9 stamps at different locations', no list",
    ),
    where=("https://www.iditarod100.org/passport-stamp-program.html",),
    reason="not published as a list: the page names no stamp location; the guide's list is a magazine page",
)
