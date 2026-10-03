"""step_form_route: each Hike Finder hike's route over the junction graph, written to derived.formed_routes for dbt to read back.

    python step_form_route.py [--warehouse data/warehouse.duckdb]

pipeline/ELT.md, "Python steps, outside dbt", is the design, and SH03 and SH06
of its ledger the rules. Forming a route is a search over the graph:
lib/hike_route_builder.py's beam over the trails a description names, routed
by lib/trail_graph_route.py, the Python twin of the phone's own router
(client/src/lib/trailGraph.ts), function for function. DuckDB 1.5.5 has no
graph extension (`duckpgq` answered HTTP 404 for it, measured 2026-10-01), a
recursive-CTE path search is @unvalidated for speed, and a search rewritten
in SQL would stop being the phone's twin, which is the reason the miles beside
a route can be trusted. So the search stays Python, and nothing else does:
the grade is int_suggested_hikes__graded's (SH04), what ships and the track
tolerance int_suggested_hikes__routed's (SH05, SH06), and the record the
suggested_hikes mart's.

THE STEP, between two dbt invocations (build_marts.py's STEPS):
1. dbt builds int_suggested_hikes__hike_finder and the graph's models;
2. this writes the graph into a temporary directory in the shape
   route_hikefinder.py reads (trail_graph.json, trail_graph_geometry.json and,
   where the climb model has rows, trail_graph_elevation.json) and loads it
   with route_hikefinder.load_graph(), keeping geometry within 15 km of every
   hike's start, so the graph a route is searched over is built by today's
   code from today's files;
3. for each hike, in number order:
   - a page with no published track: measure_route(), which is form_route()
     up to its grade;
   - a page with one: the GPX parsed by lib/hikefinder.py's parse_gpx(), the
     track measured by measure_published(), then re-walked as
     export_suggested_hikes.py's track_ends() re-walks it (rewalk(), below);
4. it writes one row per hike to derived.formed_routes.

Every number is written as its double's repr and every list as JSON, so the
SQL grades and rounds the very doubles the search produced.

THE RE-WALK (SH06), and why its sampling and its snap stay here. A published
track is handed to the phone as ends it re-routes between, so the track is
sampled every TRACK_SAMPLE_M (export_suggested_hikes.py: 400 m, @unvalidated
there), each sample pulled onto the nearest line within
router.MAX_OFF_NETWORK_M, and the walk between the samples routed. That radius
is 150 ft, trailGraph.ts's MAX_OFF_NETWORK_FEET in metres - the phone's own,
"so an end this module would accept is one the phone would too"
(lib/trail_graph_route.py) - and it is a fingertip's tolerance on a planning
zoom, @unvalidated in the client, not a measurement. The pulled-on points are
GraphPoints, an edge and a fraction along it, which only the search reads, so
they are made where the search is. The tolerance on the result (10%,
@unvalidated) is a comparison of two numbers, and that is SQL's.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import duckdb

import export_suggested_hikes as exporter
import route_hikefinder
from lib import trail_graph_route as router
from lib.hike_route_builder import measure_published, measure_route, track_gap_m
from lib.hikefinder import parse_gpx

ROOT = Path(__file__).parent
WAREHOUSE_PATH = ROOT / "data" / "warehouse.duckdb"
HIKES = "intermediate.int_suggested_hikes__hike_finder"
EDGES = "intermediate.int_trail_network__edges"
NODES = "intermediate.int_suggested_hikes__graph_nodes"
CLIMB = "intermediate.int_suggested_hikes__graph_climb"
SCHEMA = "derived"
TABLE = "formed_routes"

#: derived.formed_routes' columns, in order: what stg_derived__formed_routes stages.
COLUMNS = (
    ("hike_number", "bigint"),
    ("provenance", "varchar"),
    ("formed_problem", "varchar"),
    ("route_miles", "varchar"),
    ("start_offset_m", "varchar"),
    ("route_closed", "boolean"),
    ("retrace_ratio", "varchar"),
    ("climb_gain_ft", "varchar"),
    ("climb_loss_ft", "varchar"),
    ("route_ends", "varchar"),
    ("named_trails", "varchar"),
    ("walked_trails", "varchar"),
    ("route_checks", "varchar"),
    ("track_gap_m", "varchar"),
    ("rewalk_problem", "varchar"),
    ("rewalk_ends", "varchar"),
    ("rewalk_miles", "varchar"),
    ("rewalk_climb_gain_ft", "varchar"),
    ("rewalk_climb_loss_ft", "varchar"),
    ("climb_note", "varchar"),
    ("_loaded_at", "timestamptz"),
)


def _read(con: duckdb.DuckDBPyConnection, sql: str, relation: str) -> list[tuple]:
    try:
        return con.execute(sql).fetchall()
    except duckdb.CatalogException as missing:
        raise SystemExit(
            f"{relation} is not in the warehouse: build it with dbt first (everything but `source:derived+`), "
            f"then run this step. ({missing})"
        ) from missing


def read_hikes(con: duckdb.DuckDBPyConnection, relation: str = HIKES) -> list[dict]:
    """Every hike, in number order, as the cache entry route_hikefinder.py and the route builder read."""
    rows = _read(
        con,
        f"select hike_number, stated_miles, route_type, has_start, start_lat, start_lon, start_label, "
        f"description_json, has_published_route, gpx from {relation} order by hike_number",
        relation,
    )
    hikes = []
    for number, stated, route_type, has_start, lat, lon, label, description, published, gpx in rows:
        hikes.append(
            {
                "id": number,
                "stated_miles": stated,
                "route_type": route_type,
                "start": {"lat": lat, "lon": lon, "label": label} if has_start else None,
                "description": json.loads(description) if description else [],
                "has_published_route": bool(published),
                "gpx": gpx,
            }
        )
    return hikes


def graph_files(con: duckdb.DuckDBPyConnection, directory: Path) -> int:
    """Write the graph's models into `directory` as trail_graph.json and its two sidecars. Returns the edge count.

    The climb sidecar is written only when the climb model has rows, because
    load_graph() reads a missing one as "no climb is priced" and a short one
    as a sidecar built against another graph; both mean absent, never zero.
    """
    edges = _read(
        con,
        f"select edge_index, from_node, to_node, length_m, trail_id, source_key, name, blaze_color, geom_geojson "
        f"from {EDGES} order by edge_index",
        EDGES,
    )
    nodes = _read(con, f"select node_index, lon, lat from {NODES} order by node_index", NODES)
    climb = _read(con, f"select edge_index, gain_ft, loss_ft from {CLIMB} order by edge_index", CLIMB)
    if [row[0] for row in edges] != list(range(len(edges))):
        raise SystemExit(f"{EDGES}'s edge_index is not 0..{len(edges) - 1} in order, so no sidecar can be paired with it")
    if [row[0] for row in nodes] != list(range(len(nodes))):
        raise SystemExit(f"{NODES}'s node_index is not 0..{len(nodes) - 1} in order")
    outside = [row[0] for row in edges if not (0 <= row[1] < len(nodes) and 0 <= row[2] < len(nodes))]
    if outside:
        raise SystemExit(
            f"{len(outside)} of {len(edges)} edges in {EDGES} name a node {NODES} does not hold (edge {outside[0]} first): "
            "the graph's nodes and edges come from different builds"
        )
    document = {
        "nodes": [[lon, lat] for _, lon, lat in nodes],
        "edges": [
            {
                "from": from_node,
                "to": to_node,
                "length_m": length_m,
                "trail_id": trail_id,
                "source": source,
                "name": name,
                "blaze_color": blaze_color,
            }
            for _, from_node, to_node, length_m, trail_id, source, name, blaze_color, _ in edges
        ],
    }
    (directory / route_hikefinder.GRAPH_NAME).write_text(json.dumps(document), encoding="utf-8")
    geometry = [json.loads(geom)["coordinates"] if geom else None for *_, geom in edges]
    (directory / route_hikefinder.GEOMETRY_NAME).write_text(json.dumps(geometry), encoding="utf-8")
    if climb:
        sidecar = [None if gain is None or loss is None else [gain, loss] for _, gain, loss in climb]
        (directory / route_hikefinder.ELEVATION_NAME).write_text(json.dumps(sidecar), encoding="utf-8")
    return len(edges)


def rewalk(graph: router.Graph, points: list[tuple[float, float]]) -> tuple[tuple[list, router.Route] | None, str | None]:
    """export_suggested_hikes.py's track_ends() up to its tolerance: ((snapped points, route), None), or (None, why not).

    The same three moves in the same order: the track thinned by
    exporter.sample_track(), every sample pulled onto the nearest line within
    router.MAX_OFF_NETWORK_M (or the whole re-walk refused), and the walk the
    phone would make between them routed by router.route_through(). Whether
    that walk comes back the track's own length (TRACK_REPRODUCTION_TOLERANCE)
    is int_suggested_hikes__routed's to say.
    """
    snapped: list[router.GraphPoint] = []
    for lon, lat in exporter.sample_track(points):
        found = router.nearest_point(graph, lon, lat, max_off_m=router.MAX_OFF_NETWORK_M)
        if found is None:
            return None, (
                f"a {exporter.TRACK_SAMPLE_M:.0f} m sample at {lon:.6f}, {lat:.6f} sits more than "
                f"{router.MAX_OFF_NETWORK_M * router.FEET_PER_METRE:.0f} ft from any line this build draws"
            )
        snapped.append(found)
    if len(snapped) < 2:
        return None, "the track samples to fewer than two points"
    route = router.route_through(graph, snapped)
    if route is None:
        return None, "this build's lines hold no path between the track's samples"
    return (snapped, route), None


def _text(value: float | None) -> str | None:
    """A double as the text that reads back to it exactly, or None."""
    return None if value is None else repr(float(value))


def _ends(points) -> str:
    return json.dumps([[point[0], point[1]] for point in points])


def form(graph: router.Graph, hike: dict, loaded_at: datetime) -> tuple:
    """One hike's row of derived.formed_routes, in COLUMNS' order."""
    row = dict.fromkeys(name for name, _ in COLUMNS)
    row.update(hike_number=hike["id"], climb_note=graph.climb_note, _loaded_at=loaded_at)
    if hike["has_published_route"]:
        formed = measure_published(hike, parse_gpx(hike["gpx"]) if hike["gpx"] else None)
        row.update(provenance=formed.provenance, route_checks=json.dumps(formed.checks))
        if not formed.ends:
            row["formed_problem"] = formed.problems[0]
            return tuple(row.values())
        row.update(
            route_miles=_text(formed.miles),
            route_closed=formed.closed,
            route_ends=_ends(formed.ends),
            track_gap_m=_text(track_gap_m(formed)),
        )
        walked, why_not = rewalk(graph, [tuple(end) for end in formed.ends])
        if walked is None:
            row["rewalk_problem"] = why_not
            return tuple(row.values())
        snapped, route = walked
        row.update(rewalk_ends=_ends([point.at for point in snapped]), rewalk_miles=_text(route.miles))
        if route.climb is not None:
            row.update(rewalk_climb_gain_ft=_text(route.climb[0]), rewalk_climb_loss_ft=_text(route.climb[1]))
        return tuple(row.values())

    formed = measure_route(graph, hike)
    row.update(
        provenance=formed.provenance,
        start_offset_m=_text(formed.start_offset_m),
        named_trails=json.dumps(formed.named_trails),
        route_checks=json.dumps(formed.checks),
    )
    if formed.route is None:
        row["formed_problem"] = formed.problems[0]
        return tuple(row.values())
    row.update(
        route_miles=_text(formed.miles),
        route_closed=formed.closed,
        retrace_ratio=_text(formed.retrace_ratio),
        route_ends=_ends(formed.ends),
        walked_trails=json.dumps(formed.walked_trails),
    )
    if formed.climb is not None:
        row.update(climb_gain_ft=_text(formed.climb[0]), climb_loss_ft=_text(formed.climb[1]))
    return tuple(row.values())


def write_formed_routes(con: duckdb.DuckDBPyConnection, rows: list[tuple]) -> int:
    """Replace derived.formed_routes with these rows. Returns the row count."""
    con.execute(f"create schema if not exists {SCHEMA}")
    columns = ", ".join(f"{name} {kind}" for name, kind in COLUMNS)
    con.execute(f"create or replace table {SCHEMA}.{TABLE} ({columns})")
    if rows:
        con.executemany(f"insert into {SCHEMA}.{TABLE} values ({', '.join('?' for _ in COLUMNS)})", rows)
    return con.execute(f"select count(*) from {SCHEMA}.{TABLE}").fetchone()[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--warehouse", type=Path, default=WAREHOUSE_PATH)
    args = parser.parse_args(argv)

    loaded_at = datetime.now(UTC)
    with duckdb.connect(str(args.warehouse)) as con:
        hikes = read_hikes(con)
        with tempfile.TemporaryDirectory() as directory:
            edges = graph_files(con, Path(directory))
            starts = [(hike["start"]["lon"], hike["start"]["lat"]) for hike in hikes if hike["start"]]
            graph = route_hikefinder.load_graph(Path(directory), starts)
        rows = [form(graph, hike, loaded_at) for hike in hikes]
        written = write_formed_routes(con, rows)

    formed = sum(1 for row in rows if row[2] is None)
    print(f"step_form_route: {written} hike(s) over {edges} edge(s), {formed} with a route measured -> {SCHEMA}.{TABLE}")
    if graph.climb_note:
        print(f"  climb: {graph.climb_note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
