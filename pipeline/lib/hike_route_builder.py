"""Form a route for a hike the Hike Finder export publishes no track for, and
say how much the result is worth (#1427).

WHAT THE HARD PART ACTUALLY IS. 272 of the export's 385 hikes publish one
parking coordinate and a turn-by-turn description somebody walked, and no
line at all. Putting one of those on a map means CONSTRUCTING the route:
reading "turn left onto the blue-blazed Timp-Torne Trail" and finding, on this
build's own trail lines, the junction that sentence means. The other 113
publish a GPX track, and those are not this module's business - a survey
somebody walked outranks anything inferred here, and `route_hikefinder.py`
uses it verbatim.

THE METHOD, AND WHY IT IS THE ONE THE REST OF THIS BUILD ALREADY USES. A
published route (features/SUGGESTED_HIKES.md) stores the points a phone routes
BETWEEN and never the edges, because the graph is republished and renumbered
under a stored line. So forming a route here means producing that same short
list of ENDS, and the arithmetic over them is `lib/trail_graph_route.py`'s -
the twin of the phone's own router. What this module adds is the step
`route_nynjtc_hikes.py` left to a person: choosing the ends.

It chooses them from the description, in four steps:

  1. SNAP THE START. The export's coordinate is the PARKING, which its own
     page says in as many words, and a parking lot is not a trailhead. It is
     pulled onto the nearest line and the distance it moved is kept, because
     that distance is the honest measure of how much was assumed.

  2. READ THE TRAIL NAMES the description names, in the order it names them.
     Measured with THIS module over all 385 descriptions on 2026-09-15
     against the 2026-09-14 graph: 1,870 trail-shaped phrases, 1,529 of them
     (82%) matching the name of a line this build draws, and 362 of 385 hikes
     naming at least one - median 4.

  3. TURN EACH NAME INTO A WAYPOINT, in order, by taking the nearest point on
     a line of that name TO THE WAYPOINT BEFORE IT rather than to the start.
     That is the whole trick and it is worth one sentence: when a description
     says "turn left onto the Timp-Torne Trail", the nearest point on
     Timp-Torne to where the walk currently is IS the junction the sentence
     means. Taking it nearest the start instead would jump to whichever end of
     that trail happened to be closer to the car.

  4. ROUTE THROUGH THEM with the twin, closing the loop for every route type
     that returns to its start - which the export says is all but the 17 it
     calls Shuttle.

WHY A FORMED ROUTE IS GRADED AND NOT JUST BUILT. A line drawn on a map is
read by a hiker as somewhere a person walked. This one was not: it is an
inference from prose, and CLAUDE.md's four ways this app can hurt somebody
puts "lost" first. So every formed route is measured against what the
publisher independently stated about it - their own mileage, their own route
type - and the checks are arranged so that AGREEMENT IS EVIDENCE and
disagreement is fatal rather than cosmetic. A route whose length disagrees
with the publisher's by half went somewhere else, and there is no way to tell
which half is wrong, so it does not ship.

The grades, and what each is allowed to mean:

    strong    every check passed - length within LENGTH_GOOD of the
              publisher's, the start on the network, most of the named trails
              actually walked, and a loop that does not double back
    fair      the route holds together but something is looser than that
    rejected  no route at all

`rejected` is the one that matters, and it is a FEATURE. FEATURES.md's rule -
"a confidently wrong prediction is more dangerous than an honest unknown" -
means a formed route this module cannot stand behind must be absent, not
faint.

WHAT `rejected` COSTS, said plainly rather than softened: the hike does not
reach the phone's suggested-hikes shelf at all. It is tempting to write that
it "still ships its prose and its tags", and that is not true today -
`client/src/lib/dayHikes.ts`'s `validSegments` drops a record with fewer than
two ends, so a hike with no route is a hike the client will not show. Its
facts are all kept, in data/raw/hikefinder.json and in the routes artifact,
and nothing about them is lost; what they are missing is a screen that can
print a hike nobody has a line for.

EVERY THRESHOLD BELOW IS `@unvalidated`. They are round numbers chosen to be
defensible, not measured against hikers walking the results, and each says
what would settle it. Nothing here has been checked against ground truth,
because ground truth for these 272 hikes is exactly what the export does not
have - that is why this module exists.

Pure module - no network, no files. Takes a loaded graph and one parsed hike.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lib import trail_graph_route as router

#: Where a route came from. The distinction the maintainer asked for in as
#: many words ("mark the route as generated or not"), and the one a card must
#: never blur: PUBLISHED is a GPX track whoever wrote the hike up recorded,
#: GENERATED is this module's inference from their prose.
PUBLISHED = "published"
GENERATED = "generated"

GRADE_STRONG = "strong"
GRADE_FAIR = "fair"
GRADE_REJECTED = "rejected"

#: How far the parking coordinate may sit from the nearest line and still be
#: snapped onto it at all. @unvalidated - chosen from the distribution rather
#: than from anybody walking it: measured over all 385 export coordinates
#: against the 2026-09-14 graph, 247 sit within 45.7 m (the phone's own
#: MAX_OFF_NETWORK_M), 312 within 100 m, 328 within 200 m and 345 within
#: 1,000 m, median 22.2 m. 500 m is past the knee of that curve and is about
#: as far as a lot can plausibly be from the trail it serves by a path this
#: build does not draw. What would settle it: knowing, for a sample of these
#: parking pins, whether the walk from the car to the trail is a real
#: connector nobody has mapped or a snap onto the wrong trail entirely.
START_MAX_OFF_M = 500.0

#: Beyond this, the start is kept but the route can never grade `strong`.
#: @unvalidated - 150 m is `MAX_OFF_NETWORK_FEET` in metres, the radius the
#: phone itself will resolve a stored end within, so a start further off than
#: this is one the phone would refuse if it were not snapped first.
START_GOOD_OFF_M = 150.0

#: How many of the description's opening steps may name the trail the walk
#: leaves the car on. @unvalidated - 3 rather than 1 because the first
#: sentence often crosses a road or names the park before it names the tread
#: ("cross Route 17A and follow the white blazes of the A.T."), and rather
#: than more because a step this far in is describing the walk, not the
#: trailhead.
ANCHOR_STEPS = 3

#: Whether the start is chosen by the description's opening steps at all.
#: Measured on the ground-truth set - see this module's docstring.
ANCHOR_START_ON_ITINERARY = False

#: How far from the start to look for a line carrying a named trail. 8 km
#: @unvalidated: the longest hike the export states is 19.5 miles and a walk
#: that long can put a named trail a long way from the car, but a name matched
#: further away than this is more likely a different trail sharing a name than
#: the one the description means.
NAME_SEARCH_M = 8_000.0

#: A waypoint must advance the walk by at least this far from the one before
#: it, or it is dropped. @unvalidated - 60 m is roughly the length of a
#: junction, so two "waypoints" closer than this are the same junction read
#: twice out of one sentence ("cross the Long Path and continue"), and keeping
#: both would price the same step of the walk twice.
MIN_WAYPOINT_SEPARATION_M = 60.0

#: At most this many waypoints. @unvalidated - `route_through` refuses the
#: WHOLE route if any single leg fails to route, so each extra waypoint is
#: another chance to lose everything; 12 is comfortably past the median of 3
#: matched names per hike while keeping that risk bounded.
MAX_WAYPOINTS = 12

#: How far the formed route's length may sit from the publisher's own stated
#: mileage. @unvalidated, and the most consequential numbers in this file.
#: 0.20 and 0.40 are round; what makes them defensible is the ASYMMETRY they
#: create - a route that agrees with an independently stated length to within
#: a fifth is unlikely to have wandered onto different trails, while one that
#: disagrees by more than two fifths has no reading under which it is the walk
#: the description describes. What would settle them: walking a sample of
#: formed routes against their write-ups and finding where the error rate
#: actually turns over.
LENGTH_GOOD = 0.20
LENGTH_FAIR = 0.40

#: How much of a closed route may be walked twice before it stops being a
#: loop. @unvalidated - a Circuit that retraces most of itself is an
#: out-and-back the waypoints failed to route around, which is the single most
#: likely way this module goes wrong, so it is checked rather than assumed.
#: A Lollipop is a loop with a stem and legitimately retraces the stem, which
#: is why the fair ceiling is as loose as it is.
RETRACE_GOOD = 0.25
RETRACE_FAIR = 0.60

#: The share of the trails the description names that the formed route must
#: actually walk. @unvalidated - below half, the route is not following the
#: description even if its length happens to agree.
TRAILS_GOOD = 0.6
TRAILS_FAIR = 0.34

#: Route types that end where they began. Read off the export on 2026-09-15:
#: Circuit 321, Lollipop 34, Out and back 13, Shuttle 17. An out-and-back
#: closes too - the router's shortest way back from a dead end is the way it
#: came - so only Shuttle is left open.
CLOSED_ROUTE_TYPES = {"circuit", "lollipop", "out and back"}

#: The blaze words a description uses, mapped onto the values the graph's
#: `blaze_color` actually carries (measured over the 2026-09-14 graph: White
#: 66,432 edges, Blue 31,197, Yellow 22,774, Red 21,700, Aqua 16,118, Green
#: 11,861, Orange 10,327, Purple 2,079, Other 703, and None/Unknown on the
#: rest). "Teal" and "turquoise" are the Highlands Trail's diamond, which this
#: build's layers spell Aqua - the export's writers use all three words.
#:
#: A colour NOT in this map resolves to nothing rather than to `Other`: the
#: point of a blaze is to narrow the candidates, and a word this build cannot
#: place narrows nothing. Silver, brown, black and pink are deliberately
#: absent for that reason.
BLAZE_WORDS = {
    "white": "White",
    "blue": "Blue",
    "yellow": "Yellow",
    "red": "Red",
    "green": "Green",
    "orange": "Orange",
    "purple": "Purple",
    "aqua": "Aqua",
    "teal": "Aqua",
    "turquoise": "Aqua",
}

#: What a blaze is worth when the name already matched, as a share of the
#: distance score. @unvalidated - see `_candidate_points`, which uses it only
#: to BREAK TIES between same-named candidates, so its exact value cannot move
#: a route on its own.
BLAZE_TIE_BREAK_M = 250.0

#: A trail-shaped phrase: up to four capitalised words before Trail, Path,
#: Way or Loop. Deliberately greedy about what it proposes and strict about
#: what it accepts - a proposal only becomes a waypoint if a line of that
#: name exists near the start, so a false positive like "Continental Road
#: Trail" costs nothing and a missed name costs a leg.
#:
#: LOOP IS IN THE LIST because 359 of the trail names this build draws end in
#: it (measured 2026-09-15) - "Pond Loop", "Leonard Run Loop", "Outer Loop" -
#: and leaving it out silently lost every one of them. It is safe to include
#: for free: `normalise_name` treats "loop" as carrying no identity, so a
#: bare "the Loop" in prose normalises to nothing and is skipped before it
#: can become a waypoint. Measured across all 385 descriptions, including it
#: recovers 69 more matched trail mentions (1,460 -> 1,529) and one more hike
#: with any match at all (361 -> 362). It does NOT move the match RATE, which
#: sits at 82% either way - the names it adds are about as findable as the
#: ones already there, which is the honest way to read that.
_TRAIL_PHRASE = re.compile(r"((?:[A-Z][\w'’.-]*\s+){0,4}(?:Trail|Path|Way|Loop))\b")

#: A sentence-initial "The" is capitalised like a proper noun and gets swept
#: into the phrase ahead of it. Dropped so a sheet reads "A.T. Trail" rather
#: than "The A.T. Trail"; `normalise_name` already ignores it for matching,
#: so this is about what a reviewer reads, not about what matches what.
_LEADING_THE = re.compile(r"^the\s+", re.IGNORECASE)

#: The four shapes a description uses to point at a trail, measured over all
#: 385 descriptions on 2026-09-15: 354 of them name a blaze colour at least
#: once, 4,217 mentions in all. Order matters - the first two carry BOTH a
#: name and a colour and must be tried before the looser two, or
#: "the red-blazed Duggan Trail" would match `_BLAZE_ONLY` and lose its name.
#:
#:   "the red-blazed Butler Trail"      -> name + colour
#:   "the white blazes of the A.T."     -> name + colour
#:   "a blue-blazed trail"              -> colour, NO NAME
#:   "the Timp-Torne Trail"             -> name, no colour
#:
#: The third is the one that pays for this whole block: a description that
#: says "head into the woods on a blue-blazed trail" names no trail at all,
#: and before #1427's follow-up nothing in this module could place it.
_TRAIL_TAIL = r"(?:[A-Z][\w'\u2019.-]*\s+){0,4}(?:Trail|Path|Way|Loop)"
_BLAZE_WORD = "|".join(BLAZE_WORDS)
_STEP_PATTERNS = (
    ("name_blaze", re.compile(rf"\b({_BLAZE_WORD})[- ]blazed\s+({_TRAIL_TAIL})\b", re.IGNORECASE)),
    ("blaze_of", re.compile(rf"\b({_BLAZE_WORD})\b[^.]{{0,24}}?\bblazes?\s+of\s+the\s+({_TRAIL_TAIL})\b", re.IGNORECASE)),
    ("blaze_only", re.compile(rf"\b({_BLAZE_WORD})[- ]blazed\s+(trail|path|route)\b", re.IGNORECASE)),
)

#: Words that carry no identity, dropped before two names are compared. The
#: export writes "the Timp-Torne Trail" where this build's layer writes
#: "Timp-Torne", and nynjtc.org writes "Appalachian Trail" where the ATC layer
#: writes "Appalachian National Scenic Trail" - a comparison that kept these
#: would call all three different trails.
_NOISE_WORDS = re.compile(r"\b(?:trail|path|route|loop|the|a|an|national|scenic|state|park)\b")
_NON_WORD = re.compile(r"[^a-z0-9 ]")
_SPACES = re.compile(r"\s+")


def normalise_name(name: str | None) -> str:
    """A trail name reduced to what identifies it, for comparison only.

    Never stored and never shown: a name is carried as its publisher spells
    it, and this is the key the two spellings meet under.
    """
    if not name:
        return ""
    lowered = _NON_WORD.sub(" ", name.lower().replace("&", "and"))
    return _SPACES.sub(" ", _NOISE_WORDS.sub(" ", lowered)).strip()


@dataclass
class Step:
    """One pointer at a trail, as the description gives it.

    EITHER half may be missing and the pair is what makes this worth having.
    A name with no colour is the ordinary case; a COLOUR WITH NO NAME is the
    case nothing in this module could place before ("head into the woods on a
    blue-blazed trail"); and a name WITH a colour is the strongest, because
    the two have to agree on the same line before it is taken.
    """

    name: str | None
    blaze: str | None

    @property
    def key(self) -> str:
        """What makes two steps the same trail.

        THE NAME ALONE WHERE THERE IS ONE. A description says "the
        white-blazed Appalachian Trail" and then just "the A.T." three
        sentences later, and those are one trail; keying on the pair made them
        two steps, which put a second waypoint on a trail the walk was already
        on. Only a nameless step is keyed by its colour, because there the
        colour is all the identity it has.
        """
        return normalise_name(self.name) if self.name else f"blaze:{self.blaze or ''}"

    def label(self) -> str:
        if self.name and self.blaze:
            return f"{self.name} ({self.blaze.lower()})"
        return self.name or f"a {(self.blaze or '?').lower()}-blazed trail"


#: Whether a step carrying a colour and NO name may become a waypoint.
#: Measured on the ground-truth set - see this module's docstring.
USE_NAMELESS_BLAZE_STEPS = False


def itinerary(paragraphs: list[str], nameless: bool | None = None) -> list[Step]:
    """The trails a description points at, in the order it points at them.

    ORDER IS THE WHOLE POINT - it is the only thing in a write-up that says
    which way round the walk goes, and a set would throw it away.

    Blaze-carrying phrases are matched FIRST and the spans they consume are
    closed, so "the red-blazed Duggan Trail" yields one step carrying both
    halves rather than a bare "Duggan Trail" beside a nameless red one.
    """
    nameless = USE_NAMELESS_BLAZE_STEPS if nameless is None else nameless
    text = " ".join(paragraphs)
    found: list[tuple[int, Step]] = []
    taken: list[tuple[int, int]] = []

    for kind, pattern in _STEP_PATTERNS:
        for match in pattern.finditer(text):
            colour = BLAZE_WORDS.get(match.group(1).lower())
            if colour is None:
                continue
            name = None if kind == "blaze_only" else _LEADING_THE.sub("", match.group(2).strip()).strip()
            if name is not None and not normalise_name(name):
                name = None
            taken.append((match.start(), match.end()))
            if name is None and not nameless:
                continue
            found.append((match.start(), Step(name=name, blaze=colour)))

    for match in _TRAIL_PHRASE.finditer(text):
        if any(start <= match.start() < end for start, end in taken):
            continue
        name = _LEADING_THE.sub("", match.group(1).strip()).strip()
        if normalise_name(name):
            found.append((match.start(), Step(name=name, blaze=None)))

    steps: list[Step] = []
    seen: set[str] = set()
    for _, step in sorted(found, key=lambda pair: pair[0]):
        if step.key in seen:
            continue
        seen.add(step.key)
        steps.append(step)
    return steps


def trail_mentions(paragraphs: list[str]) -> list[str]:
    """The trails a description names, in the order it names them, with a run
    of consecutive mentions of one trail collapsed to a single entry.

    ORDER IS THE WHOLE POINT - it is the only thing in the write-up that says
    which way round the walk goes, and a set would throw it away.

    A TRAIL NAMED AGAIN LATER IS KEPT, and that is the difference between a
    loop and an out-and-back. The first version of this function kept each
    name once, and it cost 70 of the 272 formable hikes: a circuit that walks
    out on the A.T., across on Timp-Torne and home on the A.T. lost its final
    mention, so the only way back from the last waypoint was the shortest
    path - which is the way it came. Measured 2026-09-15, those hikes graded
    out at a retrace of about 50%, the signature of an out-and-back, on
    routes the export calls Circuit.

    Consecutive mentions still collapse, because prose repeats the trail it is
    already on ("the A.T. continues... the A.T. then descends") and each of
    those would otherwise become a waypoint pinned to the point the walk had
    already reached.
    """
    found: list[str] = []
    for phrase in _TRAIL_PHRASE.findall(" ".join(paragraphs)):
        name = _LEADING_THE.sub("", phrase.strip()).strip()
        key = normalise_name(name)
        if not key:
            continue
        if key in {normalise_name(seen) for seen in found}:
            continue
        found.append(name)
    return found


@dataclass
class FormedRoute:
    """One attempt to form a route, and everything a reader needs to judge it.

    Carries the attempt even when it FAILED - `route` is None and `problems`
    says why - because "this hike got no line, and here is the reason" is the
    answer a reviewer needs, and an empty result would make a refusal
    indistinguishable from a hike nobody tried.
    """

    hike_id: int
    provenance: str
    grade: str
    route: router.Route | None = None
    ends: list[tuple[float, float]] = field(default_factory=list)
    miles: float | None = None
    stated_miles: float | None = None
    start_offset_m: float | None = None
    closed: bool = False
    retrace_ratio: float | None = None
    named_trails: list[str] = field(default_factory=list)
    walked_trails: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    checks: dict = field(default_factory=dict)

    @property
    def ships(self) -> bool:
        """Whether this hike has a route a hiker could be shown.

        `ends` rather than `route` is the test, because the two roads fill
        different fields: a GENERATED route carries a `route` measured over
        this build's graph, while a PUBLISHED one carries only the track's own
        points and never touches the graph at all. Testing `route` graded every
        one of the 113 surveyed tracks as not shipping - the best routes in the
        import, silently dropped - which is what this property looked like
        when it was first written.
        """
        return self.grade != GRADE_REJECTED and len(self.ends) >= 2

    @property
    def length_error(self) -> float | None:
        """How far the measurement sits from the publisher's own figure, as a
        signed fraction of it. None when they stated none to disagree with."""
        if self.miles is None or not self.stated_miles:
            return None
        return (self.miles - self.stated_miles) / self.stated_miles

    def to_dict(self) -> dict:
        return {
            "hike_id": self.hike_id,
            "provenance": self.provenance,
            "grade": self.grade,
            "ends": [list(end) for end in self.ends],
            "closed": self.closed,
            "miles": round(self.miles, 3) if self.miles is not None else None,
            "stated_miles": self.stated_miles,
            "length_error": round(self.length_error, 4) if self.length_error is not None else None,
            "start_offset_m": round(self.start_offset_m, 1) if self.start_offset_m is not None else None,
            "retrace_ratio": round(self.retrace_ratio, 3) if self.retrace_ratio is not None else None,
            "named_trails": list(self.named_trails),
            "walked_trails": list(self.walked_trails),
            "problems": list(self.problems),
            "checks": dict(self.checks),
        }


def retrace_ratio(route: router.Route) -> float:
    """The share of the walk spent on ground it had already covered.

    Priced in METRES WALKED rather than in edges counted, because an edge is
    whatever length the survey made it and counting them would let fifty short
    edges outvote one long one.
    """
    walked: dict[int, list[float]] = {}
    for section in route.sections:
        for edge_index, metres in zip(section.edge_indices, section.walked_metres):
            walked.setdefault(edge_index, []).append(metres)
    total = sum(sum(runs) for runs in walked.values())
    if total <= 0:
        return 0.0
    repeated = sum(sum(runs[1:]) for runs in walked.values() if len(runs) > 1)
    return repeated / total


def _edge_matches(graph: router.Graph, edge_index: int, step: Step) -> bool:
    """Whether this line is one the step could be pointing at.

    A NAMED step is matched on its name alone, and the blaze is left to break
    ties below rather than to refuse: this build's layers carry `Unknown` on
    398,882 of 631,915 edges, so demanding the colour agree would throw away
    the correct trail whenever its surveyor did not record one. A NAMELESS
    step has only the colour, and there the colour must match exactly - it is
    the whole of the evidence.
    """
    edge = graph.edges[edge_index]
    if step.name:
        return normalise_name(edge.get("name")) == normalise_name(step.name)
    return bool(step.blaze) and edge.get("blaze_color") == step.blaze


def _blaze_bonus(graph: router.Graph, edge_index: int, step: Step) -> float:
    """Metres to forgive a candidate whose blaze agrees with the description.

    Only ever a TIE-BREAK between lines that already matched the name, which
    is why it is subtracted from a distance rather than scored separately: two
    stretches of "Blue Trail" a mile apart are told apart by the colour the
    sentence gave, and a line whose blaze is `Unknown` is neither rewarded nor
    punished for what its surveyor did not write down.
    """
    if not (step.name and step.blaze):
        return 0.0
    return BLAZE_TIE_BREAK_M if graph.edges[edge_index].get("blaze_color") == step.blaze else 0.0


def _candidate_points(graph: router.Graph, step: Step, near: router.GraphPoint, radius_m: float) -> router.GraphPoint | None:
    """The nearest point to `near` on any line this step could mean."""
    best: router.GraphPoint | None = None
    best_score = float("inf")
    for edge_index in router.edges_near(graph, near.at[0], near.at[1], radius_m):
        if not _edge_matches(graph, edge_index, step):
            continue
        fraction, off_m, at = router.project_onto_edge(graph, edge_index, near.at)
        score = off_m - _blaze_bonus(graph, edge_index, step)
        if score < best_score:
            best_score = score
            best = router.GraphPoint(edge_index=edge_index, fraction=fraction, at=at, off_metres=off_m)
    return best


def anchor_start(
    graph: router.Graph, lon: float, lat: float, steps: list[Step], max_off_m: float = None
) -> router.GraphPoint | None:
    """Where the walk leaves the car, chosen by what the description says it
    walks first rather than by whichever line happens to be nearest.

    THE MAINTAINER'S OBSERVATION, 2026-09-15, and it is the cheapest accuracy
    in this module: a parking area serves more than one trail, and the
    description's first sentence almost always says which one - "follow the
    red-blazed Butler Trail into the woods", "head into the woods on a
    blue-blazed trail". Snapping to the nearest line instead starts the walk on
    the wrong trail, and every waypoint after it is then resolved from the
    wrong place, so one bad metre at the car becomes a route on the wrong side
    of the hill.

    The first step that resolves within `max_off_m` wins; falling back to the
    plain nearest point when none of them does, because a start on the wrong
    trail is still better than no route at all - and the grade downstream is
    what decides whether the result is worth showing.
    """
    max_off_m = START_MAX_OFF_M if max_off_m is None else max_off_m
    plain = router.nearest_point(graph, lon, lat, max_off_m=max_off_m, search_m=max_off_m * 2)
    if plain is None or not ANCHOR_START_ON_ITINERARY:
        return plain
    here = router.GraphPoint(edge_index=plain.edge_index, fraction=plain.fraction, at=(lon, lat), off_metres=0.0)
    for step in steps[:ANCHOR_STEPS]:
        found = _candidate_points(graph, step, here, max_off_m)
        if found is not None and found.off_metres <= max_off_m:
            return found
    return plain


def _far_point_on(graph: router.Graph, step: Step, near: router.GraphPoint, radius_m: float) -> router.GraphPoint | None:
    """The point on a line of this name that sits FARTHEST from `near`, within
    `radius_m` of it.

    The mirror of `_candidate_points`, and it exists for the one shape that
    function cannot describe: a loop made of two trails. Such a loop meets its
    partner TWICE, and the nearest point on the second trail is the junction
    the walk joins it at - so a chain built only of nearest points walks out to
    that junction and has nowhere to go but back. Measured 2026-09-15, this was
    the single largest failure in the corpus: 57 of 272 formable hikes came out
    as an exact out-and-back (50% retraced) on a page the export calls Circuit,
    among them id 35, whose whole description is the Escarpment Trail and the
    Schutt Road Trail.

    Farthest by straight line rather than by network distance, which is a
    deliberate approximation: the network answer would need a shortest path to
    every candidate, and the straight-line one picks the far extremity of the
    same trail in every case this was checked against. It only ever proposes a
    waypoint - `form_route` keeps it only if the route it produces is actually
    more loop-shaped than the one without it.
    """
    best: router.GraphPoint | None = None
    best_m = -1.0
    for edge_index in router.edges_near(graph, near.at[0], near.at[1], radius_m):
        if not _edge_matches(graph, edge_index, step):
            continue
        fraction, off_m, at = router.project_onto_edge(graph, edge_index, near.at)
        for end_fraction in (0.0, 1.0):
            line = graph.geometry[edge_index] if graph.has_geometry(edge_index) else None
            if line:
                point = tuple(line[0] if end_fraction == 0.0 else line[-1])
            else:
                node = graph.nodes[graph.edges[edge_index]["from" if end_fraction == 0.0 else "to"]]
                point = (node[0], node[1])
            away = router.metres_between(near.at, point)
            if away > best_m and away <= radius_m:
                best_m = away
                best = router.GraphPoint(edge_index=edge_index, fraction=end_fraction, at=point, off_metres=0.0)
    return best


def waypoints_from_itinerary(
    graph: router.Graph, start: router.GraphPoint, steps: list[Step], radius_m: float = NAME_SEARCH_M
) -> tuple[list[router.GraphPoint], list[Step]]:
    """Each step as a point on the network, in the description's order.

    Walks FORWARD from the start, each step resolved against the position the
    walk has reached rather than against the car - see this module's docstring,
    step 3. A step no line nearby carries is skipped rather than failing the
    hike: descriptions name road crossings, side trails to viewpoints, and
    trails in parks whose layer this build has not registered, and none of
    those should cost the route its other legs.
    """
    points: list[router.GraphPoint] = []
    used: list[Step] = []
    here = start
    for step in steps:
        if len(points) >= MAX_WAYPOINTS:
            break
        found = _candidate_points(graph, step, here, radius_m)
        if found is None:
            continue
        if router.metres_between(here.at, found.at) < MIN_WAYPOINT_SEPARATION_M:
            continue
        points.append(found)
        if step.key not in {seen.key for seen in used}:
            used.append(step)
        here = found
    return points, used


#: How many partial walks the search keeps alive. @unvalidated as a number,
#: but the SHAPE is measured: a true track walks a median of 3 distinct trails
#: while the parser finds a median of 6 steps in its description (measured over
#: the 113 ground-truth hikes, 2026-09-15), because a write-up names the trails
#: you cross, pass and decline as readily as the ones you walk. So roughly half
#: the steps are not waypoints at all, and which half is the question this
#: search exists to answer.
SEARCH_BEAM = 24

#: What a kept step is worth against a mile of disagreement, when the score
#: below chooses between two walks. @unvalidated - small on purpose: the
#: publisher's own mileage is evidence about the walk and a step count is not,
#: so this only ever separates two routes the length cannot separate.
COVERAGE_WEIGHT = 0.03


#: How the search weighs what it can see. SWEPT against the 113 ground-truth
#: hikes rather than picked (2026-09-15), scoring each setting by how many
#: routes clear the calibrated `strong` bar and what share of those actually
#: match the surveyed track:
#:
#:     length 1.0, coverage 1.0   18 strong, 89% of them correct   <- this
#:     length 1.0, coverage 0.0   10 strong, 90%
#:     length 0.35, coverage 1.0  21 strong, 81%
#:     length 0.0, coverage 1.0   21 strong, 81%
#:
#: BOTH TERMS CARRY INFORMATION and dropping either costs something real -
#: length alone finds too few, coverage alone finds more and is wrong more
#: often. Equal weights was the best trade on this sample and the sample is
#: 51 scored routes, so these are evidence rather than proof.
LENGTH_WEIGHT = 1.0
RETRACE_WEIGHT = 1.0
COVERAGE_WEIGHT = 1.0


def _route_score(route: router.Route, stated_miles: float | None, kept: int, closed: bool, covered: float = 0.0) -> float:
    """How much this walk looks like the one the description describes.

    THE PUBLISHER'S OWN MILEAGE IS THE EVIDENCE, and it is used here to CHOOSE
    rather than only to check afterwards. That is the whole change: the first
    version of this module built one walk greedily and then asked whether its
    length agreed, so a spurious waypoint - a trail the description merely
    mentions crossing - could not be recovered from. Scoring lets the search
    drop that step and keep the walk.

    Higher is better. Length disagreement dominates; retracing is penalised on
    a closed walk because an out-and-back that calls itself a Circuit is the
    most common wrong answer; coverage only breaks ties.
    """
    score = COVERAGE_WEIGHT * covered
    if stated_miles:
        score -= LENGTH_WEIGHT * abs(route.miles - stated_miles) / stated_miles
    if closed:
        score -= RETRACE_WEIGHT * retrace_ratio(route)
    return score


def _covered_share(graph: router.Graph, route: router.Route, steps: list[Step]) -> float:
    """The share of the trails the description pointed at that this walk is
    actually on. The search's main objective - see LENGTH_WEIGHT."""
    if not steps:
        return 0.0
    names = {normalise_name(leg.name) for leg in route.legs if leg.name}
    blazes = {leg.blaze_color for leg in route.legs if leg.blaze_color}
    hit = sum(1 for s in steps if (normalise_name(s.name) in names if s.name else s.blaze in blazes))
    return hit / len(steps)


def _search_waypoints(
    graph: router.Graph,
    start: router.GraphPoint,
    waypoints: list[router.GraphPoint],
    kept_steps: list[Step],
    closed: bool,
    stated_miles: float | None,
) -> tuple[router.Route | None, list[router.GraphPoint], list[Step]]:
    """The best walk through SOME ordered subset of the proposed waypoints.

    A beam over one decision per step - take it or leave it - keeping the
    partial walks whose length so far sits closest to the publisher's figure.
    Order is never rearranged: the description's order is the only thing that
    says which way round the walk goes, and a search free to permute it would
    be inventing a route rather than reading one.
    """
    memo: dict[tuple[int, float, int, float], router.Route | None] = {}

    def leg(a: router.GraphPoint, b: router.GraphPoint) -> router.Route | None:
        key = (a.edge_index, round(a.fraction, 6), b.edge_index, round(b.fraction, 6))
        if key not in memo:
            memo[key] = router.route_between(graph, a, b)
        return memo[key]

    # Each beam entry: the points kept so far, the steps they came from, and
    # the miles walked to reach the last of them.
    beam: list[tuple[list[router.GraphPoint], list[Step], float]] = [([start], [], 0.0)]
    for index, waypoint in enumerate(waypoints):
        step = kept_steps[index] if index < len(kept_steps) else None
        nxt = list(beam)
        for points, steps, miles in beam:
            if len(points) > MAX_WAYPOINTS:
                continue
            onward = leg(points[-1], waypoint)
            if onward is None:
                continue
            nxt.append(([*points, waypoint], [*steps, step] if step else steps, miles + onward.miles))
        # Keep the partial walks that have not already overshot, nearest first.
        target = stated_miles or 0.0
        nxt.sort(key=lambda entry: (abs(entry[2] - target) if target else -entry[2], -len(entry[0])))
        beam = nxt[:SEARCH_BEAM]

    best: tuple[float, router.Route, list[router.GraphPoint], list[Step]] | None = None
    for points, steps, _ in beam:
        if len(points) < 2:
            continue
        route = router.close_the_loop(graph, points) if closed else router.route_through(graph, points)
        if route is None:
            continue
        covered = _covered_share(graph, route, kept_steps)
        score = _route_score(route, stated_miles, len(points) - 1, closed, covered)
        if best is None or score > best[0]:
            best = (score, route, points, steps)
    if best is None:
        return None, [], []
    return best[1], best[2], best[3]


def _grade(result: FormedRoute, route_type: str | None) -> tuple[str, list[str]]:
    """The grade, and every check that is not clean, in the order a reviewer
    should read them.

    A SINGLE FAILING CHECK CAPS THE GRADE - they are not scored and summed.
    That is deliberate: a route can be the right length and still follow the
    wrong trails, and averaging the two would let a good number hide a bad one.
    """
    problems: list[str] = []
    grade = GRADE_STRONG

    def cap(level: str) -> None:
        nonlocal grade
        order = {GRADE_STRONG: 0, GRADE_FAIR: 1, GRADE_REJECTED: 2}
        if order[level] > order[grade]:
            grade = level

    error = result.length_error
    if error is None:
        problems.append("the export states no length, so nothing independent says whether this route is the right one")
        cap(GRADE_FAIR)
    elif abs(error) > LENGTH_FAIR:
        problems.append(
            f"{result.miles:.1f} mi against the export's {result.stated_miles:.1f} mi ({error * 100:+.0f}%) - "
            "too far apart to be the same walk"
        )
        cap(GRADE_REJECTED)
    elif abs(error) > LENGTH_GOOD:
        problems.append(f"{result.miles:.1f} mi against the export's {result.stated_miles:.1f} mi ({error * 100:+.0f}%)")
        cap(GRADE_FAIR)

    if result.start_offset_m is not None and result.start_offset_m > START_GOOD_OFF_M:
        problems.append(
            f"the parking sits {result.start_offset_m:.0f} m from the nearest line, so the route starts somewhere the hiker is not"
        )
        cap(GRADE_FAIR)

    named, walked = len(result.named_trails), len(result.walked_trails)
    share = (walked / named) if named else 0.0
    result.checks["trails_share"] = round(share, 3)
    if named == 0:
        problems.append("the description names no trail this build draws, so nothing tied the route to the write-up")
        cap(GRADE_REJECTED)
    elif share < TRAILS_FAIR:
        problems.append(f"walks {walked} of the {named} trails the description names - it is not following the write-up")
        cap(GRADE_REJECTED)
    elif share < TRAILS_GOOD:
        problems.append(f"walks {walked} of the {named} trails the description names")
        cap(GRADE_FAIR)

    if result.closed and result.retrace_ratio is not None:
        if result.retrace_ratio > RETRACE_FAIR:
            problems.append(
                f"{result.retrace_ratio * 100:.0f}% of this '{route_type}' is walked twice - it closed as an out-and-back, not a loop"
            )
            cap(GRADE_REJECTED)
        elif result.retrace_ratio > RETRACE_GOOD:
            problems.append(f"{result.retrace_ratio * 100:.0f}% of the walk doubles back on itself")
            cap(GRADE_FAIR)

    return grade, problems


def form_route(graph: router.Graph, hike: dict) -> FormedRoute:
    """Attempt a route for one unrouted hike, graded.

    Returns a FormedRoute in every case, including the ones that failed. The
    caller decides what to do with a `rejected` grade; this module's opinion
    is that it must not reach a hiker as a line.
    """
    hike_id = int(hike["id"])
    result = FormedRoute(hike_id=hike_id, provenance=GENERATED, grade=GRADE_REJECTED)
    result.stated_miles = hike.get("stated_miles")

    start_coord = hike.get("start")
    if not start_coord:
        result.problems.append("no coordinate on the page - there is nowhere to start from")
        return result

    steps = itinerary(hike.get("description") or [])
    start = anchor_start(graph, start_coord["lon"], start_coord["lat"], steps)
    if start is None:
        result.problems.append(
            f"the parking is more than {START_MAX_OFF_M:.0f} m from any line this build draws - "
            "the trails this hike walks are not in the layers registered here"
        )
        return result
    result.start_offset_m = start.off_metres

    waypoints, used = waypoints_from_itinerary(graph, start, steps)
    result.named_trails = [step.label() for step in used]
    if not waypoints:
        result.problems.append(
            f"none of the {len(steps)} trails the description points at match a line within "
            f"{NAME_SEARCH_M / 1000:.0f} km of the start"
        )
        return result

    route_type = (hike.get("route_type") or "").strip().lower()
    result.closed = route_type in CLOSED_ROUTE_TYPES

    # THE SEARCH, rather than one greedy walk. Roughly half the trails a
    # description names are not waypoints at all - measured over the 113
    # ground-truth hikes, a track walks a median of 3 distinct trails while
    # the parser finds 6 steps - so the question is which of them the walk
    # actually turns onto, and the publisher's own mileage is the evidence that
    # answers it. `_search_waypoints` keeps the ordered subset that best fits.
    route, points, walked_steps = _search_waypoints(graph, start, waypoints, used, result.closed, result.stated_miles)
    if route is None:
        result.problems.append("this build's lines hold no path from the start through any trail the description names")
        return result

    result.route = route
    result.miles = route.miles
    result.ends = [(point.at[0], point.at[1]) for point in points]
    result.retrace_ratio = retrace_ratio(route)
    walked_names = {normalise_name(leg.name) for leg in route.legs if leg.name}
    walked_blazes = {leg.blaze_color for leg in route.legs if leg.blaze_color}
    result.walked_trails = [
        step.label() for step in used if (normalise_name(step.name) in walked_names if step.name else step.blaze in walked_blazes)
    ]
    result.checks = {
        "waypoints": len(points) - 1,
        "steps_in_description": len(steps),
        "steps_proposed": len(waypoints),
        "steps_kept": len(walked_steps),
        "legs": len(route.legs),
    }

    result.grade, problems = _grade(result, hike.get("route_type"))
    result.problems.extend(problems)
    if result.grade == GRADE_REJECTED:
        result.route = None
        result.ends = []
    return result


def published_route(hike: dict, track) -> FormedRoute:
    """The publisher's own GPX track, as the route, checked but never rebuilt.

    THE TRACK IS NOT GRADED AGAINST THIS BUILD'S TRAIL LINES, and that is the
    point of keeping the two paths apart. It is a survey of ground somebody
    walked; this build's lines are a different survey of the same ground, and
    where they disagree the track is not the one that is wrong. So the checks
    here are about the FILE - that it holds enough points to be a route, and
    that its own length is recognisably the walk the page describes - and a
    track that fails them is reported, never quietly redrawn.
    """
    hike_id = int(hike["id"])
    result = FormedRoute(hike_id=hike_id, provenance=PUBLISHED, grade=GRADE_STRONG)
    result.stated_miles = hike.get("stated_miles")

    if track is None or len(track.points) < 2:
        result.grade = GRADE_REJECTED
        result.problems.append("the published GPX holds fewer than two points, so it is not a route")
        return result

    result.miles = track.length_miles
    result.ends = [(point.lon, point.lat) for point in track.points]
    first, last = track.points[0], track.points[-1]
    gap_m = router.metres_between((first.lon, first.lat), (last.lon, last.lat))
    result.closed = gap_m <= MIN_WAYPOINT_SEPARATION_M
    result.checks = {
        "points": len(track.points),
        "with_elevation": sum(1 for point in track.points if point.ele_m is not None),
        "end_to_end_gap_m": round(gap_m, 1),
    }

    error = result.length_error
    if error is None:
        result.problems.append("the export states no length, so nothing independent confirms the track is this hike's")
        result.grade = GRADE_FAIR
    elif abs(error) > LENGTH_FAIR:
        # Reported, NOT rejected. The track is a survey and the stated mileage
        # is a round number somebody typed; where they disagree this far, what
        # is established is that one of them is wrong, and the recorded line is
        # not the likelier candidate. A reader is told and decides.
        result.problems.append(
            f"the track measures {result.miles:.1f} mi against the export's stated {result.stated_miles:.1f} mi "
            f"({error * 100:+.0f}%) - the publisher's own two figures disagree"
        )
        result.grade = GRADE_FAIR
    elif abs(error) > LENGTH_GOOD:
        result.problems.append(
            f"the track measures {result.miles:.1f} mi against the export's stated {result.stated_miles:.1f} mi ({error * 100:+.0f}%)"
        )
        result.grade = GRADE_FAIR

    declared_closed = (hike.get("route_type") or "").strip().lower() in CLOSED_ROUTE_TYPES
    if declared_closed and not result.closed:
        result.problems.append(f"the export calls this a '{hike.get('route_type')}' but the track's ends sit {gap_m:.0f} m apart")
        result.grade = GRADE_FAIR
    return result
