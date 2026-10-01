"""The Trail Foundation (Austin): challenges, published, and not landed (coverage audit 2026-10-01,
batch c6_regional_3).

Places on the club's own trail that a hiker visits in loops. It is the closest fit to #1780 — Let a
club publish a challenge — places on its own trails that hikers opt into and tag at camp — starting
with the ATC's A.T. Summer Bucket List in this batch, though it has no opt-in or tagging. No …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"History of the Trail Scavenger Hunt", `https://thetrailconservancy.org/programs/scavenger-hunt/` '
        "(REST `?slug=scavenger-hunt`, modified 2023-09-21). It has 3 loops of 5 clue locations, 15 places in "
        "all, along the Butler Trail: Johnson Creek Trailhead, Clay Pit, Opossum Temple & Voodoo Pew, Lou Neff "
        "Point, Oldest Tree on the Trail, Miro Rivera Restroom, Vista Point, Seaholm Intake, Stevie Ray "
        "Vaughan, Town Lake Gazebo, Longhorn Dam, Peace Point, Boardwalk, Lake Full and Holly Area. Hikers "
        '"scan the QR code at each location to reveal your clue". There are 16 PDFs: the printable map …',
    ),
    where=(
        "https://thetrailconservancy.org/programs/scavenger-hunt/",
        "https://thetrailfoundation.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
