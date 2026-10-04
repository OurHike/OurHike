"""Waldo County Trails Coalition: trail lines, published as the Hills to Sea Trail's section map PDFs, and not
landed (decision 54, wave 4, read live 2026-10-04).

The maps page links the full-extent map and six section PDFs, Illustrator files of 5 MB or so each (Section 3,
5,234,479 bytes, the coverage audit 2026-10-01), and offers them in the Avenza app. The coverage audit found
geospatial markers in one (`LGIDict`, `Measure`, `GPTS`), so the maps are probably georeferenced: a GDAL-based
reader could take their line art as vectors, and requirements-extract.in pins no GDAL, so here they are a PDF
only a person can read. ArcGIS Online has no "Hills to Sea" item (the coverage audit).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "robots.txt (Squarespace's, our agent allowed), then /maps, read 2026-10-04 under lib/user_agent.py's agent: "
        "200, 194,599 bytes, linking /s/H2S_FullExtent_4download_20220106-hhf9.pdf and the six section PDFs "
        "(H2S_Section1_20220106.pdf, H2S_Section2_20210503.pdf, H2S_Section3_2025.pdf, H2S_Section4_2025.pdf, "
        "H2S_Section5_20220106.pdf, H2S_Section6_20210623.pdf); no KML, GPX or GeoJSON is linked.",
        "the coverage audit (2026-10-01, batch c4_regional_1): Section 3 is 5,234,479 bytes, Illustrator, 1 page, "
        "with 3 geospatial-marker hits; ArcGIS has 0 results for 'Hills to Sea'.",
    ),
    where=("https://www.hillstosea.org/maps",),
    reason="a PDF only a person can read here: georeferenced line art needs a GDAL reader the extract does not pin",
)
