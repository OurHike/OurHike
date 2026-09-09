"""Measure every NYNJTC Favorite Hike's constructed route against the current
junction graph, and render the sheet a person signs it off from (#1290).

    python route_nynjtc_hikes.py                       measure, print the table, write the review sheet
    python route_nynjtc_hikes.py --graph-dir DIR       read trail_graph*.json from DIR instead of data/processed
    python route_nynjtc_hikes.py --review PATH         write the sheet somewhere other than data/processed

WHAT THE HARD PART ACTUALLY IS. NYNJTC publishes, for each hike, a pin for
the trailhead and a turn-by-turn description a person walked. They publish
no line - no GPX, no KML, no layer (the maintainer confirmed there is none to
find). Putting one of these on the map therefore means CONSTRUCTING the
route: reading "turn left onto the red-blazed Catfish Loop Trail" and
finding, on this build's own trail lines, the junction that sentence means.
That is a judgement, so it lives where judgements live: each hike's ends are
a row in reference/nynjtc_hike_routes.json, placed by hand from the
description with lib/trail_graph_route.py's junction search, and this script
is the arithmetic that checks the row rather than the thing that wrote it.

WHY ENDS, NOT A LINE. A published route (features/SUGGESTED_HIKES.md) stores
the points a phone routes BETWEEN and never the edges, for the reason a
saved day hike does (lib/dayHikes.ts: "never persist edgeIndex") - the
graph is republished and renumbered, and a stored line would go stale under
it. So what a row holds is three to five snapped coordinates in walking
order, and what a phone draws is `routeThrough` over them. The miles and
climb this prints are lib/trail_graph_route.py's, the Python twin of that
call, so the number beside a card is the number the phone will redo.

WHAT THE SHEET IS FOR. Every `proposed` row waits for a person: the
maintainer's rule was "let me see the edits and approve first". The sheet
draws each route over the trails around it, lists the legs by trail name
and blaze, prints the measured miles beside NYNJTC's own, and says what was
excluded and why. Reading it is the review; flipping a row to `reviewed` is
the sign-off; export_suggested_hikes.py ships nothing else.

THE FIGURES ARE MEASURED, AND THE ONE THAT IS NOT IS SAID. Miles are the
twin's over this graph's lines, which differ from NYNJTC's counts by the
digitisation of somebody's survey and by whatever the route leaves out
(each row's `basis` names the side trips not on any line). Climb is priced
only from a trail_graph_elevation.json that fits this graph, and is
otherwise reported as unknown - lib/trail_graph_route.py's docstring has the
production measurement that makes this a rule rather than a caution.

NO NETWORK. Reads data/raw/nynjtc_hikes.json (fetch_nynjtc_hikes.py),
data/processed/trail_graph*.json (build_trail_graph.py and
export_network_elevation.py) and the reference file. Exits non-zero when a
`reviewed` row no longer routes: a person signed those ends off against a
graph that has since moved, and that is a publish-time problem the exporter
refuses on too, surfaced here first.
"""

from __future__ import annotations

import html
import json
import sys
from datetime import date
from pathlib import Path

from lib import trail_graph_route as router

ROOT = Path(__file__).resolve().parent
CACHE_PATH = ROOT / "data" / "raw" / "nynjtc_hikes.json"
PROCESSED_DIR = ROOT / "data" / "processed"
REFERENCE_PATH = ROOT / "reference" / "nynjtc_hike_routes.json"
REVIEW_PATH = PROCESSED_DIR / "nynjtc_hike_routes_review.html"

GRAPH_NAME = "trail_graph.json"
GEOMETRY_NAME = "trail_graph_geometry.json"
ELEVATION_NAME = "trail_graph_elevation.json"

STATUS_PROPOSED = "proposed"
STATUS_REVIEWED = "reviewed"
STATUS_HELD = "held"
STATUSES = (STATUS_PROPOSED, STATUS_REVIEWED, STATUS_HELD)

#: How far a stored end may sit from the line and still resolve - the
#: phone's own radius (lib/trail_graph_route.py MAX_OFF_NETWORK_M). Ends are
#: stored snapped, so a real value here is a few centimetres; the ceiling is
#: what catches a republished line that moved out from under a row.
END_SNAP_M = router.MAX_OFF_NETWORK_M

#: Geometry is kept only this far around the hikes' ends. 12 km covers the
#: longest published route (the 13-mile Platte Clove out-and-back spans
#: 7 km end to end) with room for the trails drawn around it.
KEEP_RADIUS_M = 12_000

#: The sketch draws every line within this distance of the route's bounding
#: box, in grey, so a reviewer sees the junctions the route did not take.
CONTEXT_MARGIN_M = 600


def load_routes(path: Path | None = None) -> dict:
    """The reference rows, validated: an unknown status is a typo that would
    otherwise read as 'not reviewed' and silently hold a signed-off hike."""
    path = REFERENCE_PATH if path is None else path
    if not path.exists():
        raise SystemExit(f"{path} is missing - the reviewed rows are this script's whole subject")
    document = json.loads(path.read_text(encoding="utf-8"))
    routes = document.get("routes") or {}
    for slug, row in routes.items():
        if row.get("status") not in STATUSES:
            raise SystemExit(f"{path.name}: {slug} has status {row.get('status')!r}, expected one of {STATUSES}")
        if row["status"] != STATUS_HELD and not (isinstance(row.get("ends"), list) and len(row["ends"]) >= 2):
            raise SystemExit(f"{path.name}: {slug} is {row['status']} but carries fewer than two ends")
    return routes


def load_cache(path: Path | None = None) -> dict:
    path = CACHE_PATH if path is None else path
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("hikes") or {}
    except (OSError, ValueError):
        return {}


def all_ends(routes: dict) -> list[tuple[float, float]]:
    points = []
    for row in routes.values():
        for end in row.get("ends") or []:
            points.append((float(end[0]), float(end[1])))
    return points


def load_graph(graph_dir: Path, routes: dict) -> router.Graph:
    graph_path = graph_dir / GRAPH_NAME
    if not graph_path.exists():
        raise SystemExit(f"{graph_path} is missing - run build_trail_graph.py first; nothing can be measured without the graph")
    return router.load_graph(
        graph_path,
        graph_dir / GEOMETRY_NAME,
        graph_dir / ELEVATION_NAME,
        keep_near=all_ends(routes) or None,
        keep_radius_m=KEEP_RADIUS_M,
    )


def snap_ends(graph: router.Graph, row: dict) -> tuple[list[router.GraphPoint], list[str]]:
    """Every end as a point on the line, or the problems that stop it."""
    points, problems = [], []
    for at, end in enumerate(row.get("ends") or []):
        found = router.nearest_point(graph, float(end[0]), float(end[1]), max_off_m=END_SNAP_M)
        if found is None:
            problems.append(
                f"end {at + 1} at {end[0]:.5f},{end[1]:.5f} is more than {END_SNAP_M:.0f} m from any line on this build"
            )
            continue
        points.append(found)
    return points, problems


def measure(graph: router.Graph, row: dict) -> dict:
    """One row against the graph: the route, or what stopped it."""
    points, problems = snap_ends(graph, row)
    if problems:
        return {"route": None, "points": points, "problems": problems}
    route = router.close_the_loop(graph, points) if row.get("closed") else router.route_through(graph, points)
    if route is None:
        return {"route": None, "points": points, "problems": ["no path on this build's lines between two consecutive ends"]}
    return {"route": route, "points": points, "problems": []}


def drift(measured: float, recorded: float | None) -> float | None:
    """How far this run's miles sit from the figure the row was placed at."""
    if recorded is None or recorded <= 0:
        return None
    return (measured - recorded) / recorded


def published_miles(row: dict, hike: dict | None) -> float | None:
    """NYNJTC's own length: the row's override where the parse picked the
    wrong number, else what lib/nynjtc_hikes.py read off the overview."""
    if row.get("published_miles") is not None:
        return float(row["published_miles"])
    if hike and hike.get("stated_miles") is not None:
        return float(hike["stated_miles"])
    return None


# --- the sheet -----------------------------------------------------------------


def _bbox(lines: list[list]) -> tuple[float, float, float, float]:
    xs = [pt[0] for line in lines for pt in line]
    ys = [pt[1] for line in lines for pt in line]
    return min(xs), min(ys), max(xs), max(ys)


def _context_lines(
    graph: router.Graph, bbox: tuple[float, float, float, float], route_edges: set[int]
) -> list[tuple[list, str | None]]:
    """Every drawn line within the margin of the route's box, minus the route."""
    west, south, east, north = bbox
    deg = CONTEXT_MARGIN_M / 111_000
    centre = ((west + east) / 2, (south + north) / 2)
    radius = router.metres_between((west, south), (east, north)) / 2 + CONTEXT_MARGIN_M
    found = []
    for edge_index in router.edges_near(graph, centre[0], centre[1], radius):
        if edge_index in route_edges or not graph.has_geometry(edge_index):
            continue
        line = graph.geometry[edge_index]
        if all(pt[0] < west - deg or pt[0] > east + deg or pt[1] < south - deg or pt[1] > north + deg for pt in line):
            continue
        found.append((line, graph.edges[edge_index].get("name")))
    return found


def sketch_svg(
    graph: router.Graph, route: router.Route, points: list[router.GraphPoint], width: int = 520, height: int = 400
) -> str:
    """The route in ink over its neighbourhood in grey, numbered ends, a
    scale bar. Plain SVG, no map tiles: the point is the topology a reviewer
    checks against the description, not the scenery."""
    lines = router.route_lines(graph, route)
    if not lines:
        return "<p class='muted'>No geometry loaded for this route, so nothing to draw.</p>"
    bbox = _bbox(lines)
    context = _context_lines(graph, bbox, set(route.edge_indices))
    west, south, east, north = bbox
    pad_deg = CONTEXT_MARGIN_M / 111_000
    west, east, south, north = west - pad_deg, east + pad_deg, south - pad_deg, north + pad_deg
    span_x = router.metres_between((west, south), (east, south)) or 1
    span_y = router.metres_between((west, south), (west, north)) or 1
    scale = min((width - 20) / span_x, (height - 20) / span_y)

    def project(pt) -> tuple[float, float]:
        x = router.metres_between((west, south), (pt[0], south)) * scale + 10
        y = height - 10 - router.metres_between((west, south), (west, pt[1])) * scale
        return x, y

    def path(line) -> str:
        return "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in (project(pt) for pt in line))

    parts = [f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="Route sketch">']
    parts.append(f'<rect width="{width}" height="{height}" fill="#f7f3e9"/>')
    for line, _ in context:
        parts.append(f'<path d="{path(line)}" fill="none" stroke="#c3baa4" stroke-width="1.5" stroke-linecap="round"/>')
    for line in lines:
        parts.append(
            f'<path d="{path(line)}" fill="none" stroke="#122016" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" opacity="0.9"/>'
        )
    for line in lines:
        parts.append(
            f'<path d="{path(line)}" fill="none" stroke="#355c3a" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
        )
    for number, point in enumerate(points, start=1):
        x, y = project(point.at)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="#fffdf7" stroke="#355c3a" stroke-width="2"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{y + 4:.1f}" text-anchor="middle" font-family="IBM Plex Mono, monospace" font-size="11" fill="#355c3a">{number}</text>'
        )
    bar = 500 * scale
    parts.append(f'<line x1="14" y1="{height - 14}" x2="{14 + bar:.1f}" y2="{height - 14}" stroke="#2b2620" stroke-width="2"/>')
    parts.append(
        f'<text x="14" y="{height - 20}" font-family="IBM Plex Mono, monospace" font-size="10" fill="#5a5346">500 m</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def _fmt_miles(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f} mi"


def render_sheet(results: list[dict], graph: router.Graph, today: str) -> str:
    """The whole review, one card per hike, proposed first."""
    order = {STATUS_PROPOSED: 0, STATUS_REVIEWED: 1, STATUS_HELD: 2}
    results = sorted(results, key=lambda r: (order[r["status"]], r["name"].casefold()))
    counts = {status: sum(1 for r in results if r["status"] == status) for status in STATUSES}
    cards = []
    for result in results:
        row, hike = result["row"], result["hike"]
        name = html.escape(result["name"])
        head = f"<h2>{name}</h2>"
        meta = []
        if hike:
            meta.append(html.escape(hike.get("difficulty") or "no difficulty"))
            for term in hike.get("terms", {}).get("route-type", []):
                meta.append(html.escape(term["name"]))
            for term in hike.get("terms", {}).get("park", []):
                meta.append(html.escape(term["name"]))
            meta.append(f'<a href="{html.escape(hike["source_url"])}">nynjtc.org ›</a>')
        head += "<p class='meta'>" + " · ".join(meta) + "</p>"
        if result["status"] == STATUS_HELD:
            cards.append(
                f"<section class='card held'>{head}<p class='status'>HELD</p><p>{html.escape(row.get('reason', ''))}</p></section>"
            )
            continue
        route = result["route"]
        body = [head, f"<p class='status'>{result['status'].upper()}</p>"]
        if route is None:
            body.append(
                "<p class='problem'>Does not route on this build: "
                + "; ".join(html.escape(p) for p in result["problems"])
                + "</p>"
            )
        else:
            published = result["published_miles"]
            figure = f"<strong>{_fmt_miles(route.miles)}</strong> measured on this build's lines"
            if published is not None:
                delta = (route.miles - published) / published * 100
                figure += f" · NYNJTC says {_fmt_miles(published)} ({delta:+.0f}%)"
            climb = f"+{route.climb[0]:.0f} / −{route.climb[1]:.0f} ft" if route.climb else "climb unknown"
            body.append(f"<p class='figures'>{figure} · {climb} · {len(route.legs)} legs</p>")
            if result["drift"] is not None and abs(result["drift"]) > 0.03:
                body.append(
                    f"<p class='problem'>Moved {result['drift'] * 100:+.0f}% since the row was placed at {row.get('measured_miles')} mi - the ground under it has been republished; re-read the sketch.</p>"
                )
            body.append(sketch_svg(graph, route, result["points"]))
            legs = "".join(
                f"<li><span class='mono'>{leg.miles:5.2f} mi</span> {html.escape(leg.name or 'unnamed')} <span class='muted'>({html.escape(str(leg.blaze_color))} · {html.escape(str(leg.source))})</span></li>"
                for leg in route.legs
            )
            body.append(f"<ol class='legs'>{legs}</ol>")
        body.append(f"<p class='basis'><span class='label'>Basis</span> {html.escape(row.get('basis', ''))}</p>")
        if row.get("published_miles_note"):
            body.append(
                f"<p class='basis'><span class='label'>NYNJTC's figure</span> {html.escape(row['published_miles_note'])}</p>"
            )
        ends = " → ".join(f"{e[1]:.5f}, {e[0]:.5f}" for e in row["ends"]) + (" → back to 1" if row.get("closed") else "")
        body.append(f"<p class='mono small'>{ends}</p>")
        cards.append("<section class='card'>" + "".join(body) + "</section>")

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>NYNJTC Route Sign-off</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bitter:wght@600&amp;family=Public+Sans:wght@400;600&amp;family=IBM+Plex+Mono:wght@400;500&amp;display=swap">
<style>
body{{margin:0;padding:24px;background:#e6e0d0;color:#2b2620;font-family:'Public Sans',ui-sans-serif,system-ui,sans-serif;font-size:14px;line-height:1.45}}
h1{{font-family:Bitter,ui-serif,Georgia,serif;font-size:22px;margin:0 0 4px}} h2{{font-family:Bitter,ui-serif,Georgia,serif;font-size:18px;margin:0 0 4px}}
.intro{{max-width:760px;margin-bottom:20px}} .card{{background:#fffdf7;border:1px solid #e4ddca;border-radius:14px;padding:16px;margin:0 0 16px;max-width:760px}}
.held{{background:#f7f3e9}} .status{{display:inline-block;font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:#8a5a1a;background:#fbeed9;border:1px solid #d69a2d;border-radius:999px;padding:2px 10px;margin:0 0 8px}}
.held .status{{color:#5a5346;background:#e4ddca;border-color:#c3baa4}} .meta{{margin:0 0 8px;color:#5a5346}} .figures{{margin:0 0 10px}} .problem{{color:#994e15;margin:0 0 10px}}
.legs{{margin:10px 0;padding-left:20px}} .legs li{{margin:2px 0}} .mono{{font-family:'IBM Plex Mono',ui-monospace,monospace}} .small{{font-size:11px;color:#8a8271}} .muted{{color:#8a8271}}
.basis{{margin:8px 0 0;color:#5a5346}} .label{{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:#8a8271;margin-right:6px}} svg{{display:block;width:100%;max-width:100%;height:auto;border:1px solid #e4ddca;border-radius:8px}}
a{{color:#355c3a}}
</style></head><body>
<h1>NYNJTC Favorite Hikes — the routes OurHike built, for sign-off</h1>
<div class="intro"><p>{counts[STATUS_PROPOSED]} proposed · {counts[STATUS_REVIEWED]} reviewed · {counts[STATUS_HELD]} held. Measured {today} on this build's trail lines by the pipeline's twin of the phone's router. Ink is the route as the phone will draw it between the numbered ends; grey is every other line nearby. NYNJTC's own length sits beside each measurement so they can disagree in the open.</p>
<p class="muted">{html.escape(graph.climb_note or "Climb priced from trail_graph_elevation.json.")}</p></div>
{"".join(cards)}
</body></html>"""


def build_results(graph: router.Graph, routes: dict, cache: dict) -> list[dict]:
    results = []
    for slug, row in routes.items():
        hike = cache.get(slug)
        name = hike["name"] if hike else slug
        if row["status"] == STATUS_HELD:
            results.append(
                {
                    "slug": slug,
                    "name": name,
                    "row": row,
                    "hike": hike,
                    "status": STATUS_HELD,
                    "route": None,
                    "points": [],
                    "problems": [],
                    "published_miles": None,
                    "drift": None,
                }
            )
            continue
        measured = measure(graph, row)
        route = measured["route"]
        results.append(
            {
                "slug": slug,
                "name": name,
                "row": row,
                "hike": hike,
                "status": row["status"],
                "route": route,
                "points": measured["points"],
                "problems": measured["problems"],
                "published_miles": published_miles(row, hike),
                "drift": drift(route.miles, row.get("measured_miles")) if route else None,
            }
        )
    return results


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    graph_dir = PROCESSED_DIR
    review_path = REVIEW_PATH
    if "--graph-dir" in argv:
        graph_dir = Path(argv[argv.index("--graph-dir") + 1])
    if "--review" in argv:
        review_path = Path(argv[argv.index("--review") + 1])

    routes = load_routes()
    cache = load_cache()
    if not cache:
        print(f"No cached hikes at {CACHE_PATH} - run fetch_nynjtc_hikes.py first; the sheet will name rows by slug.")
    graph = load_graph(graph_dir, routes)
    if graph.climb_note:
        print(f"climb: {graph.climb_note}")

    results = build_results(graph, routes, cache)
    failed_reviewed = []
    for result in results:
        if result["status"] == STATUS_HELD:
            print(f"  held      {result['slug'][:60]}")
            continue
        route = result["route"]
        if route is None:
            print(f"  {result['status']:9} {result['slug'][:60]}  DOES NOT ROUTE: {'; '.join(result['problems'])}")
            if result["status"] == STATUS_REVIEWED:
                failed_reviewed.append(result["slug"])
            continue
        published = result["published_miles"]
        beside = f"NYNJTC {published:.2f}" if published is not None else "NYNJTC ?"
        climb = f"+{route.climb[0]:.0f}/-{route.climb[1]:.0f} ft" if route.climb else "climb unknown"
        moved = (
            f"  moved {result['drift'] * 100:+.0f}% since placed"
            if result["drift"] is not None and abs(result["drift"]) > 0.03
            else ""
        )
        print(
            f"  {result['status']:9} {result['slug'][:60]}  {route.miles:5.2f} mi ({beside})  {climb}  {len(route.legs)} legs{moved}"
        )

    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(render_sheet(results, graph, date.today().isoformat()), encoding="utf-8")
    print(f"-> {review_path}")

    if failed_reviewed:
        print(
            f"{len(failed_reviewed)} reviewed row(s) no longer route on this build: {', '.join(failed_reviewed)}", file=sys.stderr
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
