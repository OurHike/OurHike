"""Maine Huts & Trails: points of interest, held. A candidate steward with no approved trail_orgs.json row, so it lives
in _shared/ under the folder its row would name (decision 122, the maintainer's poll, 2026-10-09: "Every type,
held"), beside closures.py; when the row is approved this file moves to the club folder of the same name.

- `maine_huts_huts`: the 4 huts, one page each (mainehuts.org/hut/<slug>/, the pages its hut-sitemap.xml lists),
  through extract/_pages_points.py's parse_maine_huts_hut (P12: the maintainer, 2026-10-11, chose "build a page
  reader"). Each page's own map script centres on the hut, `var hut = { lat, lng, zoom: 14 }`, which is the point a
  row lands, read 2026-10-11 under lib/user_agent.py's agent after mainehuts.org's robots.txt (no rule refuses the
  hut pages, no Crawl-delay): Grand Falls Hut (closed, by its own <h1>), Flagstaff Lake Hut, Stratton Brook Hut and
  Poplar Stream Hut.

A MAP CENTRE IS NOT A MARKER: the pages draw no marker (its code is commented out), so every row says
`geometry_basis: page_map_centre`, and how far each centre sits from its hut is @unvalidated (the parser says
what would settle it). Nothing is geocoded from the office address the footer prints. The row is held, and an
untyped `kind` publishes nothing: sources.json's row says why.
"""

from extract._pages_points import page_points

TYPE = "points_of_interest"
CLAIMS = ("maine_huts_huts",)
RESOURCES = [page_points(key) for key in CLAIMS]
