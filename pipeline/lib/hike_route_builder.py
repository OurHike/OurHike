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


def _candidate_points(graph: router.Graph, name_key: str, near: router.GraphPoint, radius_m: float) -> router.GraphPoint | None:
    """The nearest point to `near` on any line whose name matches `name_key`."""
    best: router.GraphPoint | None = None
    for edge_index in router.edges_near(graph, near.at[0], near.at[1], radius_m):
        if normalise_name(graph.edges[edge_index].get("name")) != name_key:
            continue
        fraction, off_m, at = router.project_onto_edge(graph, edge_index, near.at)
        if best is None or off_m < best.off_metres:
            best = router.GraphPoint(edge_index=edge_index, fraction=fraction, at=at, off_metres=off_m)
    return best


def _far_point_on(graph: router.Graph, name_key: str, near: router.GraphPoint, radius_m: float) -> router.GraphPoint | None:
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
        if normalise_name(graph.edges[edge_index].get("name")) != name_key:
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


def waypoints_from_description(
    graph: router.Graph, start: router.GraphPoint, names: list[str], radius_m: float = NAME_SEARCH_M
) -> tuple[list[router.GraphPoint], list[str]]:
    """Each named trail as a point on the network, in the description's order.

    Walks FORWARD from the start, each name resolved against the position the
    walk has reached rather than against the car - see this module's docstring,
    step 3. A name no line nearby carries is skipped rather than failing the
    hike: descriptions name road crossings, side trails to viewpoints, and
    trails in parks whose layer this build has not registered, and none of
    those should cost the route its other legs.
    """
    points: list[router.GraphPoint] = []
    used: list[str] = []
    here = start
    for name in names:
        if len(points) >= MAX_WAYPOINTS:
            break
        key = normalise_name(name)
        found = _candidate_points(graph, key, here, radius_m)
        if found is None:
            continue
        if router.metres_between(here.at, found.at) < MIN_WAYPOINT_SEPARATION_M:
            continue
        points.append(found)
        if name not in used:
            used.append(name)
        here = found
    return points, used


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

    start = router.nearest_point(
        graph, start_coord["lon"], start_coord["lat"], max_off_m=START_MAX_OFF_M, search_m=START_MAX_OFF_M * 2
    )
    if start is None:
        result.problems.append(
            f"the parking is more than {START_MAX_OFF_M:.0f} m from any line this build draws - "
            "the trails this hike walks are not in the layers registered here"
        )
        return result
    result.start_offset_m = start.off_metres

    names = trail_mentions(hike.get("description") or [])
    waypoints, used = waypoints_from_description(graph, start, names)
    result.named_trails = used
    if not waypoints:
        result.problems.append(
            f"none of the {len(names)} trail names in the description match a line within "
            f"{NAME_SEARCH_M / 1000:.0f} km of the start"
        )
        return result

    route_type = (hike.get("route_type") or "").strip().lower()
    result.closed = route_type in CLOSED_ROUTE_TYPES

    # A waypoint this build's lines cannot be reached from is DROPPED rather
    # than fatal. `route_through` refuses a whole route if any single leg
    # fails, which is right for a reviewed row - a hole in a signed-off walk
    # is a hiker told something false - but wrong here, where one unreachable
    # side trail would throw away a walk the other six waypoints describe
    # perfectly well. How many were dropped is carried into the checks, so a
    # route held together by dropping half its waypoints is visible as that.
    points = [start]
    dropped = 0
    for waypoint in waypoints:
        if router.route_between(graph, points[-1], waypoint) is None:
            dropped += 1
            continue
        points.append(waypoint)
    if len(points) < 2:
        result.problems.append("this build's lines hold no path from the start to any trail the description names")
        return result

    route = router.close_the_loop(graph, points) if result.closed else router.route_through(graph, points)
    if route is None:
        result.problems.append("this build's lines hold no path between two consecutive points of the walk")
        return result

    # THE LOOP REPAIR. A closed walk whose chain of junctions leaves it short
    # of halfway round has only one way home - the way it came - so the route
    # comes out as an exact out-and-back on a page that says Circuit. Where
    # that happened, try once more with the far extremity of the last trail the
    # description names appended, which is the second junction a two-trail loop
    # turns on. The repair is KEPT ONLY IF IT IS ACTUALLY MORE LOOP-SHAPED:
    # both candidates are measured and the one with less retracing wins, so a
    # hike this makes worse keeps the route it already had.
    repaired = 0
    if result.closed and retrace_ratio(route) > RETRACE_GOOD and used:
        far = _far_point_on(graph, normalise_name(used[-1]), points[-1], NAME_SEARCH_M)
        if far is not None and router.metres_between(points[-1].at, far.at) >= MIN_WAYPOINT_SEPARATION_M:
            candidate_points = [*points, far]
            candidate = router.close_the_loop(graph, candidate_points)
            if candidate is not None and retrace_ratio(candidate) < retrace_ratio(route):
                route, points, repaired = candidate, candidate_points, 1

    result.route = route
    result.miles = route.miles
    result.ends = [(point.at[0], point.at[1]) for point in points]
    result.retrace_ratio = retrace_ratio(route)
    walked_keys = {normalise_name(leg.name) for leg in route.legs if leg.name}
    result.walked_trails = [name for name in used if normalise_name(name) in walked_keys]
    result.checks = {
        "waypoints": len(points) - 1,
        "waypoints_dropped": dropped,
        "loop_repaired": repaired,
        "names_in_description": len(names),
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
