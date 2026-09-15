"""Give every hike in the Hike Finder export a route where one can be had
honestly, and say for each which kind of route it got (#1427).

    python route_hikefinder.py                     measure everything, write the artifact and the sheet
    python route_hikefinder.py --graph-dir DIR     read trail_graph*.json from DIR instead of data/processed
    python route_hikefinder.py --review PATH       write the sheet somewhere other than data/processed
    python route_hikefinder.py --only 1,2,3        just these hike ids, for a quick look

TWO ROADS, AND THE WHOLE POINT IS THAT THEY STAY APART.

  PUBLISHED. 113 of the export's 385 hikes carry a GPX track the publisher
  recorded. That track IS the route. It is not snapped to this build's trail
  lines, not re-routed, not smoothed: it is somebody's survey of ground they
  walked, and where it disagrees with this build's lines it is not the one
  that is wrong. What is checked is the FILE - that it holds enough points to
  be a route, that its own measured length is recognisably the walk the page
  states, and that a page calling itself a Circuit has a track whose ends meet.

  GENERATED. The other 272 publish a parking pin and a turn-by-turn
  description. `lib/hike_route_builder.py` forms a route from those over the
  junction graph, and grades it against everything the publisher independently
  said about the walk. A route that cannot be stood behind gets NO LINE, and
  today that means the hike does not reach the shelf either: the client drops
  a record with fewer than two ends (dayHikes.ts `validSegments`). Its facts
  are kept here in full; what is missing is a screen for a hike nobody has a
  line for.

WHAT THIS RUN MEASURED, 2026-09-15, against the 2026-09-14 production graph
(631,915 edges): of 272 formable hikes, 43 graded `strong`, 111 `fair` and 118
`rejected`. The grade is CALIBRATED rather than chosen - see
`lib/hike_route_builder.py`'s `_grade`, which was fitted against the 113 hikes
that publish both a description and the track the publisher drew, and selects
routes matching the publisher's drawn line 92% of the time.

The rejections are honest rather than tunable: 44 walks cannot be fitted to the
length the publisher states within 40%; 31 trailheads sit more than 500 m from
any line in the layers registered here, which is New Jersey's state and county
parks mostly (#1293); 17 find no path on this build's lines and 17 name no
trail within reach of the start; 6 walk too few of the trails they name; 3
close as an out-and-back.

THE ONE NUMBER WORTH CARRYING FORWARD is that accuracy tracks how much the
description says, not how hard the search tries. Median absolute disagreement
with the publisher's own stated mileage, by how many waypoints the description
yielded: 0.70 at one waypoint, 0.41 at two, 0.44 at three, 0.36 at four, 0.26
at six, 0.13 at eight. The signed median across all 194 formed routes is +0.02,
so the error is symmetric noise rather than a systematic shortfall - this
method is INFORMATION-LIMITED, and the way to more routes is more trail names
in the layers, not a cleverer search.

THE SHEET IS FOR A PERSON. Every generated route that would ship is drawn over
the trails around it, with its legs, its measured miles beside the export's
own, and every check that is not clean. Reading it is the review. A published
track is drawn from its own points, and is on the sheet to be LOOKED at rather
than approved - it does not wait for anybody.

NO NETWORK. Reads data/raw/hikefinder.json and data/raw/hikefinder_gpx/
(fetch_hikefinder.py) and data/processed/trail_graph*.json (build_trail_graph
.py). Writes the routes artifact and the sheet. Exits non-zero only when it
cannot run at all - a hike with no route is this script's ordinary output, not
its failure.
"""

from __future__ import annotations

import html
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from lib import trail_graph_route as router
from lib.hike_route_builder import (
    GENERATED,
    GRADE_FAIR,
    GRADE_REJECTED,
    GRADE_STRONG,
    PUBLISHED,
    form_route,
    published_route,
)
from lib.hikefinder import SOURCE_KEY, parse_gpx
from lib.stamps import utc_stamp

ROOT = Path(__file__).resolve().parent
CACHE_PATH = ROOT / "data" / "raw" / "hikefinder.json"
GPX_DIR = ROOT / "data" / "raw" / "hikefinder_gpx"
PROCESSED_DIR = ROOT / "data" / "processed"
OUT_PATH = PROCESSED_DIR / "hikefinder_routes.json"
REVIEW_PATH = PROCESSED_DIR / "hikefinder_routes_review.html"

GRAPH_NAME = "trail_graph.json"
GEOMETRY_NAME = "trail_graph_geometry.json"
ELEVATION_NAME = "trail_graph_elevation.json"

#: Geometry is kept only this far around the hikes' trailheads. 15 km covers
#: the longest walk the export states (19.5 miles) from a car park at its
#: centre, with room for the trails drawn around it.
KEEP_RADIUS_M = 15_000

#: The sketch draws every line within this distance of the route's bounding
#: box, in grey, so a reviewer sees the junctions the route did not take.
CONTEXT_MARGIN_M = 600

#: How many generated routes get a drawn sketch. @unvalidated - a sketch is
#: about 4 KB of inline SVG and the sheet is opened in a browser, so this is a
#: page-weight ceiling rather than a claim about how many need looking at;
#: every route is on the sheet either way, and the ones past this cap carry
#: their figures and legs without the picture.
MAX_SKETCHES = 120


def load_cache(path: Path | None = None) -> dict:
    path = CACHE_PATH if path is None else path
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("hikes") or {}
    except (OSError, ValueError):
        return {}


def load_track(hike: dict, gpx_dir: Path):
    """The cached GPX for one hike, parsed, or None when there is none."""
    name = hike.get("gpx_file")
    if not name:
        return None
    path = gpx_dir / name
    if not path.exists():
        return None
    return parse_gpx(path.read_text(encoding="utf-8"))


def load_graph(graph_dir: Path, starts: list[tuple[float, float]]) -> router.Graph:
    graph_path = graph_dir / GRAPH_NAME
    if not graph_path.exists():
        raise SystemExit(f"{graph_path} is missing - run build_trail_graph.py first; nothing can be formed without the graph")
    return router.load_graph(
        graph_path,
        graph_dir / GEOMETRY_NAME,
        graph_dir / ELEVATION_NAME,
        keep_near=starts or None,
        keep_radius_m=KEEP_RADIUS_M,
    )


def build_results(graph: router.Graph, cache: dict, gpx_dir: Path, only: set[int] | None = None) -> list[dict]:
    """Every hike in the cache with the best route it can honestly have."""
    results = []
    for key in sorted(cache, key=lambda k: int(k)):
        hike = cache[key]
        if only is not None and int(key) not in only:
            continue
        if hike.get("has_published_route"):
            formed = published_route(hike, load_track(hike, gpx_dir))
        else:
            formed = form_route(graph, hike)
        results.append({"hike": hike, "formed": formed})
    return results


# --- the sheet -----------------------------------------------------------------


def _bbox(lines: list[list]) -> tuple[float, float, float, float]:
    xs = [pt[0] for line in lines for pt in line]
    ys = [pt[1] for line in lines for pt in line]
    return min(xs), min(ys), max(xs), max(ys)


def _context_lines(graph: router.Graph, bbox: tuple[float, float, float, float], route_edges: set[int]) -> list[list]:
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
        found.append(line)
    return found


def sketch_svg(
    lines: list[list], context: list[list], marks: list[tuple[float, float]], width: int = 520, height: int = 380
) -> str:
    """A route in ink over its neighbourhood in grey, with a scale bar.

    Plain SVG, no map tiles - the point is the shape a reviewer checks against
    the description, not the scenery. Takes drawn lines rather than a Route, so
    a published GPX track and a generated walk over the graph are drawn by the
    same code and can be compared by eye without one of them flattering itself.
    """
    if not lines:
        return "<p class='muted'>Nothing to draw.</p>"
    west, south, east, north = _bbox(lines)
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
    for line in context:
        parts.append(f'<path d="{path(line)}" fill="none" stroke="#c3baa4" stroke-width="1.5" stroke-linecap="round"/>')
    for line in lines:
        parts.append(
            f'<path d="{path(line)}" fill="none" stroke="#122016" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" opacity="0.9"/>'
        )
    for line in lines:
        parts.append(
            f'<path d="{path(line)}" fill="none" stroke="#355c3a" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
        )
    for number, mark in enumerate(marks, start=1):
        x, y = project(mark)
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


def _card(result: dict, graph: router.Graph, draw: bool) -> str:
    hike, formed = result["hike"], result["formed"]
    name = html.escape(hike["name"])
    meta = " · ".join(
        html.escape(str(value))
        for value in (hike.get("difficulty"), hike.get("route_type"), hike.get("park"), hike.get("region"))
        if value
    )
    tags = "".join(f"<span class='tag'>{html.escape(tag)}</span>" for tag in hike.get("features") or [])
    body = [
        f"<h2>{name}</h2>",
        f"<p class='meta'>{meta} · <a href='{html.escape(hike['source_url'])}'>hike.php?id={hike['id']} ›</a></p>",
        f"<p class='status {formed.grade}'>{formed.provenance.upper()} · {formed.grade.upper()}</p>",
    ]
    if tags:
        body.append(f"<p class='tags'>{tags}</p>")

    if formed.miles is not None:
        figure = f"<strong>{formed.miles:.2f} mi</strong>"
        figure += " on the published track" if formed.provenance == PUBLISHED else " on this build's lines"
        if formed.stated_miles:
            figure += f" · the export states {formed.stated_miles:.1f} mi ({(formed.length_error or 0) * 100:+.0f}%)"
        body.append(f"<p class='figures'>{figure}</p>")

    if draw and formed.route is not None:
        lines = router.route_lines(graph, formed.route) or []
        context = _context_lines(graph, _bbox(lines), set(formed.route.edge_indices)) if lines else []
        body.append(sketch_svg(lines, context, list(formed.ends)))
        legs = "".join(
            f"<li><span class='mono'>{leg.miles:5.2f} mi</span> {html.escape(leg.name or 'unnamed')} "
            f"<span class='muted'>({html.escape(str(leg.blaze_color))} · {html.escape(str(leg.source))})</span></li>"
            for leg in formed.route.legs
        )
        body.append(f"<ol class='legs'>{legs}</ol>")
    elif draw and formed.provenance == PUBLISHED and formed.ends:
        body.append(sketch_svg([[list(point) for point in formed.ends]], [], [formed.ends[0], formed.ends[-1]]))

    if formed.named_trails:
        body.append(
            "<p class='basis'><span class='label'>Trails named</span> "
            + html.escape(", ".join(formed.named_trails))
            + (f" — walked {len(formed.walked_trails)} of {len(formed.named_trails)}" if formed.walked_trails else "")
            + "</p>"
        )
    if formed.checks:
        body.append(
            "<p class='basis'><span class='label'>Checks</span> "
            + html.escape(", ".join(f"{key.replace('_', ' ')} {value}" for key, value in formed.checks.items()))
            + "</p>"
        )
    for problem in formed.problems:
        body.append(f"<p class='problem'>{html.escape(problem)}</p>")
    if not formed.ships:
        body.append(
            "<p class='problem'><strong>No route ships for this hike</strong>, so it does not reach the shelf either — "
            "the client needs two ends to show a record. Everything the page says is still cached.</p>"
        )
    return "<section class='card'>" + "".join(body) + "</section>"


def render_sheet(results: list[dict], graph: router.Graph, today: str, counts: dict) -> str:
    """The whole review, one card per hike: what shipped, what did not, and
    why. Generated routes first, because they are the ones that were inferred
    and the only ones a person's eye can improve."""
    order = {GRADE_STRONG: 0, GRADE_FAIR: 1, GRADE_REJECTED: 2}
    ranked = sorted(
        results,
        key=lambda r: (r["formed"].provenance != GENERATED, order[r["formed"].grade], r["hike"]["name"].casefold()),
    )
    cards = []
    drawn = 0
    for result in ranked:
        draw = drawn < MAX_SKETCHES and result["formed"].ships
        cards.append(_card(result, graph, draw))
        if draw:
            drawn += 1

    summary = " · ".join(f"{value} {key}" for key, value in counts.items())
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Hike Finder routes — what shipped and what did not</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bitter:wght@600&amp;family=Public+Sans:wght@400;600&amp;family=IBM+Plex+Mono:wght@400;500&amp;display=swap">
<style>
body{{margin:0;padding:24px;background:#e6e0d0;color:#2b2620;font-family:'Public Sans',ui-sans-serif,system-ui,sans-serif;font-size:14px;line-height:1.45}}
h1{{font-family:Bitter,ui-serif,Georgia,serif;font-size:22px;margin:0 0 4px}} h2{{font-family:Bitter,ui-serif,Georgia,serif;font-size:18px;margin:0 0 4px}}
.intro{{max-width:760px;margin-bottom:20px}} .card{{background:#fffdf7;border:1px solid #e4ddca;border-radius:14px;padding:16px;margin:0 0 16px;max-width:760px}}
.status{{display:inline-block;font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:#8a5a1a;background:#fbeed9;border:1px solid #d69a2d;border-radius:999px;padding:2px 10px;margin:0 0 8px}}
.status.strong{{color:#1f5130;background:#e3f0e4;border-color:#5b9a6a}} .status.rejected{{color:#7c3a12;background:#f6e2d6;border-color:#c07a4a}}
.meta{{margin:0 0 8px;color:#5a5346}} .figures{{margin:0 0 10px}} .problem{{color:#994e15;margin:6px 0 0}}
.tags{{margin:0 0 10px}} .tag{{display:inline-block;font-size:11px;background:#eee8d8;border:1px solid #d9d1bb;border-radius:999px;padding:1px 8px;margin:0 4px 4px 0}}
.legs{{margin:10px 0;padding-left:20px}} .legs li{{margin:2px 0}} .mono{{font-family:'IBM Plex Mono',ui-monospace,monospace}} .muted{{color:#8a8271}}
.basis{{margin:8px 0 0;color:#5a5346}} .label{{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:#8a8271;margin-right:6px}}
svg{{display:block;width:100%;max-width:100%;height:auto;border:1px solid #e4ddca;border-radius:8px}} a{{color:#355c3a}}
</style></head><body>
<h1>NYNJTC Hike Finder — the route each hike got, and what it rests on</h1>
<div class="intro"><p>{summary}. Measured {today} on this build's trail lines by the pipeline's twin of the phone's router.</p>
<p><strong>PUBLISHED</strong> is the track the publisher recorded, drawn from its own points and not snapped to anything here. <strong>GENERATED</strong> was formed from the trailhead and the turn-by-turn description over this build's junction graph — it is an inference, and the grade says how much of one. A card saying <em>no route ships</em> is the honest answer for that hike — and today it also means the hike does not reach the shelf, because the client drops a record with fewer than two ends. Its facts are all kept here.</p>
<p class="muted">{html.escape(graph.climb_note or "Climb priced from trail_graph_elevation.json.")}</p></div>
{"".join(cards)}
</body></html>"""


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    graph_dir = PROCESSED_DIR
    review_path = REVIEW_PATH
    only = None
    if "--graph-dir" in argv:
        graph_dir = Path(argv[argv.index("--graph-dir") + 1])
    if "--review" in argv:
        review_path = Path(argv[argv.index("--review") + 1])
    if "--only" in argv:
        only = {int(part) for part in argv[argv.index("--only") + 1].split(",") if part.strip()}

    cache = load_cache()
    if not cache:
        raise SystemExit(f"No cached hikes at {CACHE_PATH} - run fetch_hikefinder.py first")

    starts = [
        (hike["start"]["lon"], hike["start"]["lat"])
        for hike in cache.values()
        if hike.get("start") and (only is None or int(hike["id"]) in only)
    ]
    graph = load_graph(graph_dir, starts)
    if graph.climb_note:
        print(f"climb: {graph.climb_note}")

    results = build_results(graph, cache, GPX_DIR, only)
    counts: dict[str, int] = {}
    for result in results:
        formed = result["formed"]
        counts[f"{formed.provenance}/{formed.grade}"] = counts.get(f"{formed.provenance}/{formed.grade}", 0) + 1

    document = {
        "generated_at": utc_stamp(datetime.now(timezone.utc)),
        "source": SOURCE_KEY,
        "graph": {"edges": len(graph.edges), "climb_note": graph.climb_note},
        "counts": counts,
        "routes": {str(result["hike"]["id"]): result["formed"].to_dict() for result in results},
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for result in sorted(results, key=lambda r: (r["formed"].provenance != GENERATED, r["formed"].grade)):
        formed, hike = result["formed"], result["hike"]
        miles = f"{formed.miles:5.2f} mi" if formed.miles is not None else "   no route"
        stated = f"(states {formed.stated_miles:.1f})" if formed.stated_miles else "(states ?)"
        print(f"  {formed.provenance:9} {formed.grade:8} {str(hike['id']):>4}  {hike['name'][:46]:46} {miles} {stated}")

    ships = sum(1 for result in results if result["formed"].ships)
    print(f"\n{ships} of {len(results)} hikes have a route that ships:")
    for key in sorted(counts):
        print(f"  {counts[key]:4}  {key}")
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(render_sheet(results, graph, date.today().isoformat(), counts), encoding="utf-8")
    print(f"-> {OUT_PATH}")
    print(f"-> {review_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
