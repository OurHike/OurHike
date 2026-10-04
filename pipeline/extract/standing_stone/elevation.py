"""Standing Stone Trail Club: elevation, published as a PDF of profile images, not landed.

"A PDF image, not data" (coverage audit 2026-10-01, batch c8_regional_5),
measured on 2026-10-04 (decision 54's wave 4): two pages, one image each and
no text layer, so no reader can take an elevation from it. A PDF only a
person can read stays a note. USGS 3DEP (_shared/usgs/) is the data path.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        'HEAD 2026-10-03, after robots.txt: "Elevation Profiles", '
        "`https://www.standingstonetrail.org/_files/ugd/30a84d_c0fcf7a229a64ae5b1b65623fe6fb97b.pdf`, "
        "application/pdf, 2,512,468 bytes, Last-Modified 2022-12-18",
        "GET 2026-10-04 under lib/user_agent.py's agent, after robots.txt (Wix's; no Crawl-delay for our agent): "
        "2 pages, each one image and 0 characters of text to pypdf",
    ),
    where=("https://www.standingstonetrail.org/_files/ugd/30a84d_c0fcf7a229a64ae5b1b65623fe6fb97b.pdf",),
    reason="a PDF of drawn profiles, not data: decision 54's wave 4 keeps a PDF only a person can read as a note",
)
