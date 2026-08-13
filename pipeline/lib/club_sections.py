"""Which club maintains which stretch of trail (#594, features/CORRIDOR_VIEW.md).

Thirty clubs maintain the A.T., and until now nothing downstream said so. This
turns ATC's per-segment attribution into mile ranges the corridor view can draw
and the waypoint card can cite.

Pure module - no I/O, no network. export_club_sections.py wires it up.

WHERE THE ATTRIBUTION COMES FROM, AND WHY NOT THE OBVIOUS PLACE

`trail_club_sections` is thirty polygons, one per club, and is the layer this
work was scoped around. It is not the source used here. `centerline` - which
the pipeline already fetches, already exports, and already ships to a phone -
carries `Trail_Club`, `Acronym` and `Reg_Acro` on every one of its 3,025
features. Measured 2026-08-13 against both live services:

  - centerline last edited **2026-08-04**; trail_club_sections **2024-08-15**.
    Maintaining assignments change, and a two-year-old answer presented as
    current is the kind of quiet falsehood this app exists not to make.
  - The attribution is on the trail LINE, so a mile range is read off it
    rather than derived by testing points against polygons.

The polygon layer is still read, for one job only: it is the authority on how
a club's name is SPELLED, and on its region. See CANONICAL_FROM_POLYGONS.

WHAT IS WRONG WITH THE UPSTREAM DATA, MEASURED RATHER THAN ASSUMED

The centerline's freshness is bought at a cost in cleanliness. Of 44 distinct
`Acronym` values, only 30 are clubs:

  - **47 features carry a numeric string** in BOTH `Trail_Club` and `Acronym`
    ("23", "11", "27", ...) - an unjoined FID or a shifted column upstream.
    That is 41.4 miles, 1.90% of the trail. Those miles are published as
    UNATTRIBUTED rather than filled in from the older polygon layer: a stretch
    the fresh source cannot name should say so, not borrow a two-year-old
    answer and present it as current.
  - **Two clubs are misspelt** in `Trail_Club` and correct in `Acronym`:
    "Potomac Appalachain Trail Club" (PATC) and "New York - New Jersey Trail
    Conference" (NYNJTC, spacing). Every acronym maps to exactly one spelling,
    which is what makes the acronym a safe key and the name an unsafe one.

Recorded in ../SOURCE_SURVEY.md as well, since that is where a future reader
looks to find out whether a source can be trusted.
"""

from __future__ import annotations

from dataclasses import dataclass

# Half-mile points sit ON the trail, so the nearest centerline vertex is metres
# away. This is generous by two orders of magnitude on purpose: it is a sanity
# bound that catches a milepost in the wrong state, not a tuning parameter, and
# a milepost genuinely off-corridor should come back unattributed rather than
# be snapped to whatever line happens to be nearest.
MILEPOST_SNAP_M = 100.0

# Mileposts are every half mile, so consecutive ones differ by 0.5. A gap wider
# than this ends a stretch - which is what makes a club maintaining two
# separate pieces of trail publish as two stretches rather than as one that
# falsely spans the club in between. Four clubs on the A.T. are like this;
# ATC's own club map draws them with one label point each.
STRETCH_GAP_MILES = 0.75

# Half of the milepost spacing, and the reason a stretch is not published as
# first-milepost-to-last-milepost.
#
# A milepost is a SAMPLE, not a boundary. Reporting a run as [first, last]
# silently discards half a mile per run, because a run of n mileposts spans
# (n-1) x 0.5 miles between its ends while standing for n x 0.5 miles of
# trail. Measured: that lost 44.0 of the trail's 2,197.5 miles across 87 runs,
# and published two zero-length stretches where a lone milepost sat between
# two broken features.
#
# So each milepost owns the quarter mile either side of it. Runs then tile the
# trail exactly - a club ending at mile X and the next beginning at X + 0.5
# both land on X + 0.25, abutting rather than overlapping or leaving a seam -
# and the published total comes to 4,395 x 0.5 = 2,197.5.
MILEPOST_HALF_WIDTH = 0.25

# Mile 0 is Springer, which is what `Measure` counts from.
SPRINGER_MILE = 0.0

# The polygon layer's fields. `ACROYNM` is ATC's spelling, not a typo here.
POLYGON_ACRONYM_FIELD = "ACROYNM"
POLYGON_NAME_FIELD = "TRAIL_CLUB"
POLYGON_REGION_FIELD = "REGION"

# The centerline's fields.
CENTERLINE_ACRONYM_FIELD = "Acronym"
CENTERLINE_NAME_FIELD = "Trail_Club"
CENTERLINE_REGION_FIELD = "Reg_Acro"

CANONICAL_FROM_POLYGONS = """The polygon layer supplies the display name and region for an acronym the
CENTERLINE has already assigned. It never decides WHICH stretch belongs to a
club - that is the fresh source's job, and this is the stale one. The
distinction is the whole reason the misspelt names above do not reach a hiker
while the 41 unattributed miles still read as unattributed."""


@dataclass(frozen=True)
class Club:
    """One maintaining club, and the stretches it looks after."""

    acronym: str
    name: str
    region: str | None
    stretches: tuple[tuple[float, float], ...]
    """(start_mile, end_mile) pairs, south to north, never overlapping."""

    @property
    def miles(self) -> float:
        return sum(end - start for start, end in self.stretches)


def is_attributable(acronym: object) -> bool:
    """Whether an `Acronym` value names a club at all.

    The 47 broken features carry a digit string here, and a digit string is
    never a club acronym - so this is a total test rather than a blocklist of
    the twelve values seen on one day. A thirteenth appearing next month is
    already handled.
    """
    if not isinstance(acronym, str):
        return False
    stripped = acronym.strip()
    return bool(stripped) and not stripped.isdigit()


def canonical_clubs(polygon_features: list[dict]) -> dict[str, dict]:
    """acronym -> {"name", "region"}, from the thirty-polygon layer.

    Read CANONICAL_FROM_POLYGONS before extending this: it is a spelling
    authority, not an attribution one.
    """
    canonical: dict[str, dict] = {}
    for feature in polygon_features:
        properties = feature.get("properties") or {}
        acronym = properties.get(POLYGON_ACRONYM_FIELD)
        if not is_attributable(acronym):
            continue
        canonical[acronym.strip()] = {
            "name": properties.get(POLYGON_NAME_FIELD),
            "region": properties.get(POLYGON_REGION_FIELD),
        }
    return canonical


def build_stretches(mile_acronyms: list[tuple[float, str | None]]) -> dict[str, list[tuple[float, float]]]:
    """Contiguous mile runs per acronym, from (mile, acronym) mileposts.

    Each run is widened by MILEPOST_HALF_WIDTH at both ends - read that
    constant before changing it, since the naive version loses half a mile per
    run and the loss is invisible until the totals are added up.

    Unattributed mileposts are carried under the `None` key rather than
    dropped, so the caller can publish what is NOT known as explicitly as what
    is. Dropping them would make 25 miles of trail simply absent, which reads
    as "no data here" rather than as "this source could not name it".
    """
    runs: dict[str, list[tuple[float, float]]] = {}
    current_key: str | None = ""
    start = previous = 0.0

    if not mile_acronyms:
        return runs

    def flush() -> None:
        if current_key != "":
            runs.setdefault(current_key, []).append((start - MILEPOST_HALF_WIDTH, previous + MILEPOST_HALF_WIDTH))

    for mile, acronym in sorted(mile_acronyms, key=lambda pair: pair[0]):
        broken = acronym != current_key or (mile - previous) > STRETCH_GAP_MILES
        if broken:
            flush()
            current_key, start = acronym, mile
        previous = mile
    flush()

    # The half-width leaves the first milepost's span starting a quarter mile
    # NORTH of Springer and the last one's ending a quarter mile PAST Katahdin,
    # because the mileposts begin at 0.5 rather than at 0. Neither is trail
    # anybody can walk, and a client drawing the published range would draw
    # past the terminus at one end and leave a gap at the other.
    #
    # So the two outermost spans are pinned to the termini. Total mileage is
    # unchanged - the south end gains the quarter mile the north end gives up.
    _pin_to_termini(runs, northern_terminus=max(mile for mile, _ in mile_acronyms))
    return runs


def _pin_to_termini(runs: dict[str, list[tuple[float, float]]], northern_terminus: float) -> None:
    """Extend the southernmost span to mile 0 and truncate the northernmost to
    the last milepost, in place."""
    spans = [(key, index) for key, values in runs.items() for index in range(len(values))]
    if not spans:
        return
    southernmost = min(spans, key=lambda ref: runs[ref[0]][ref[1]][0])
    northernmost = max(spans, key=lambda ref: runs[ref[0]][ref[1]][1])

    key, index = southernmost
    runs[key][index] = (SPRINGER_MILE, runs[key][index][1])
    key, index = northernmost
    runs[key][index] = (runs[key][index][0], northern_terminus)


def assemble(
    mile_acronyms: list[tuple[float, str | None]],
    canonical: dict[str, dict],
) -> tuple[list[Club], list[tuple[float, float]]]:
    """The published shape: clubs south to north, plus the unattributed runs.

    A club the centerline names but the polygon layer has never heard of keeps
    its acronym as its name rather than being dropped. That case cannot happen
    against today's data - the thirty agree - and dropping a real stretch of
    trail because a stale lookup table lacks a row is the wrong failure to
    choose in advance.
    """
    runs = build_stretches(mile_acronyms)
    unattributed = runs.pop(None, [])

    clubs = [
        Club(
            acronym=acronym,
            name=(canonical.get(acronym) or {}).get("name") or acronym,
            region=(canonical.get(acronym) or {}).get("region"),
            stretches=tuple(stretches),
        )
        for acronym, stretches in runs.items()
    ]
    clubs.sort(key=lambda club: (club.stretches[0][0], club.acronym))
    return clubs, unattributed
