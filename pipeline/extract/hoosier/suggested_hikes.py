"""Hoosier Hikers Council: suggested hikes, published as a PDF table whose text layer runs its columns
together, and not landed (decision 54 wave 4, section K, 2026-10-04).

Bicentennial_Trail_List.pdf (the 2016 Bicentennial Challenge's trail list, updated 2020-02-02, 8 pages) is a table
of trail, property, land manager, county, miles, region and link, but its text layer joins the cells with spaces
and wraps them across lines ('Tecumseh Trail Morgan-Monroe/Yellowwood' / 'SF IDNR Forestry' / 'Morgan,'), and
several rows have no miles, so no parser can tell where a trail's name ends and its property's begins. The PDF's
metadata names a person by e-mail address, which is not quoted here.

The note this replaces read, whole:

Hoosier Hikers Council: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): 18 trail pages under the Trails menu (pages). The Tecumseh Trail
Guide PDF. `/assets/Bicentennial_Trail_List.pdf` (2,078,142 bytes, "Updated: Feb. 2, 2020"), a table of
trail, property, county and miles.

Its `where`: https://hoosierhikerscouncil.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://hoosierhikerscouncil.org/assets/Bicentennial_Trail_List.pdf (HTTP 200, 2,078,142 bytes, Last-Modified 2020-02-03, no ETag, 2026-10-04): 8 pages; page 2 on, the table's cells joined in each line",
    ),
    where=("https://hoosierhikerscouncil.org/assets/Bicentennial_Trail_List.pdf",),
    reason="a PDF only a person can read: the table's text layer joins and wraps its cells",
)
