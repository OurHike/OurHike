"""Waldo County Trails Coalition: points of interest, published, and not landed (decision 54, wave 4, read live
2026-10-04): the parking areas and kiosks are symbols on the Hills to Sea Trail's section map PDFs.

Each section PDF's legend reads "Parking area · Parking: Plowed in winter · Parking: Roadside or limited · Trail
information" (the coverage audit, 2026-10-01), and the symbols are drawings. The coverage audit found
geospatial markers in one (`LGIDict`, `Measure`, `GPTS`), so the maps are probably georeferenced PDFs, whose
vector content a GDAL-based reader could place; requirements-extract.in pins no GDAL, so here they are a PDF
only a person can read. waldo/trail_lines.py records the same files for the line.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "robots.txt (Squarespace's: `User-agent: *` disallows /config, /search, /api/, /static/ and query-string "
        "views; named AI crawlers, not ours, are refused), then /maps, read 2026-10-04 under lib/user_agent.py's "
        "agent: 200, 194,599 bytes, linking the full map and six section PDFs (H2S_Section1_20220106.pdf to "
        "H2S_Section6_20210623.pdf, Section 3 and 4 dated 2025); no coordinate in the page.",
        "the coverage audit (2026-10-01, batch c4_regional_1): Section 3's legend; 3 geospatial-marker hits.",
    ),
    where=("https://www.hillstosea.org/maps", "https://www.hillstosea.org/closures"),
    reason="a PDF only a person can read here: georeferenced map symbols need a GDAL reader the extract does not pin",
)
