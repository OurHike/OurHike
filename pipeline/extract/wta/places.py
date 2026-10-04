"""Washington Trails Association: places, a page of land managers' telephone numbers with no place, not landed
(decision 54, wave 5, read live 2026-10-04).

`/go-outside/ranger-station-info` lists Washington's land managers and their offices (each National Forest's
headquarters and ranger districts, the Park Service, the state agencies) with a telephone number and links,
and no address or coordinate. An office with no place is nothing this pipeline can draw, and a telephone
number never loads (ELT.md, "Who may publish", rule 8). The offices are the agencies' own, which their own
layers carry (usgs_structures_ranger_stations and usfs_ranger_districts among them). `/go-outside/passes` is about passes and permits, not
places. The association's terms, quoted on wta/points_of_interest.py, are the maintainer's to rule on first.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "www.wta.org/robots.txt (`Crawl-delay: 60`, honoured), then /go-outside/ranger-station-info, read "
        "2026-10-04 under lib/user_agent.py's agent: 200, 114,104 bytes; office names with telephone numbers and "
        "links, no address or coordinate (the leaflet bundle the page loads is the site's, with no marker on it).",
        "the coverage audit (2026-10-01, batch c7_regional_4): `/go-outside/ranger-station-info` and "
        "`/go-outside/passes`; the hike pages' region taxonomy.",
    ),
    where=("https://www.wta.org/go-outside/ranger-station-info", "https://www.wta.org/our-work/about/terms-of-service"),
    reason="published with no place: offices and telephone numbers, never an address or a coordinate",
)
