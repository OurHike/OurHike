"""Dartmouth Outing Club: closures, nothing published (coverage audit 2026-10-01, batch p09_persist).

Folders: `usfs/` (WMNF alerts and the roads table, both pages), `nps/`, `atc`. The roads table is
the one place the access road to DOC's Moosilauke Ravine Lodge gets a status.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Tried: (2) AGOL "Dartmouth Outing Club" gave 3 hits: a clubhouse floor-plan DWG layer and an image '
        '(`f000pcb_Dartmouth`), and "The Dartmouth Fifty 23X". Dartmouth\'s org `ajkPMiuiqxF9xEgP` was searched '
        "for trail, closure, Moosilauke, Outing, cabin and Appalachian. It has 18 trail items, all on personal "
        'student or staff accounts (including "Appalachian Trail DOC Managed" by a personal ArcGIS account), '
        "and none is a closure layer. Hub: 2 hits. (3) NH GRANIT: an AGOL search for GRANIT closures gave 0 "
        "(only NH Fish & Game's `NH_Recreational_Trails`). (4) Land managers: the WMNF alerts page …",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://dartmouth.edu/",
    ),
)
