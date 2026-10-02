"""step_node_lines: cut every routable trail line where the graph says to, written to derived.graph_pieces for dbt to read back.

    python step_node_lines.py [--warehouse data/warehouse.duckdb]

pipeline/ELT.md, "Python steps, outside dbt", is the design, and TN04 of its
ledger the rule: the junction graph's pieces must be "the ones `substring`
made, to the bit" (build_trail_graph.py's _split_all docstring), because an
edge's geometry and length feed a day hike's distance. DuckDB's ST_Node
exists but is not that, so the cutting stays Python, and stays
build_trail_graph.py's own functions rather than a copy of them. Everything
around it is SQL:

1. dbt builds int_trail_network__routable (the parts a route may run on,
   TN01-TN03) and int_trail_network__cuts (which pairs cross, and which line
   ends stop short of another line, TN05);
2. this reads both and asks shapely for each cut's point, as node_lines()
   asks it: every point where a crossing pair meets (_intersection_points(),
   a shared segment's two ends), and for each end that stops short, where it
   lands on the other line (`target.interpolate(target.project(end))`);
3. it cuts every part at its points with build_trail_graph._split_all and
   writes one row per piece (`piece`), and one per landing (`landing`), the
   point a joined end welds to, to derived.graph_pieces;
4. dbt builds everything downstream of the `derived` source: the node grid
   and the welds (TN06, int_trail_network__node_lookups), the edges (TN07)
   and the two graph files (TN08).

THE SAME LINES, PROJECTED THE SAME WAY. build() projects each part with
shapely.ops.transform(pyproj Transformer EPSG:4326 -> EPSG:5070, always_xy),
and so does this, from the part's lon/lat as the routable model holds it.

A CUT SHAPELY WOULD NOT MAKE STOPS THE STEP. The decisions are the SQL's; this
re-asks shapely the predicate behind each one before cutting (a crossing pair
intersects; a joined end lies within the tolerance of a line it does not
cross) and refuses the whole run if they disagree, rather than writing a
junction the reference would not have.

Geometry goes into the table as GeoJSON text, which json.dumps writes at the
shortest length that reads back to the same double, so every vertex reaches
dbt exactly.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import numpy as np
import shapely
from shapely.geometry import Point
from shapely.ops import transform

import build_trail_graph

ROOT = Path(__file__).parent
WAREHOUSE_PATH = ROOT / "data" / "warehouse.duckdb"
PARTS = "intermediate.int_trail_network__routable"
CUTS = "intermediate.int_trail_network__cuts"
SCHEMA = "derived"
TABLE = "graph_pieces"


def read_inputs(con: duckdb.DuckDBPyConnection) -> tuple[list[dict], list[dict], float]:
    """The routable parts in part_order, the cuts in cut_order, and the endpoint tolerance the cuts were judged at."""
    try:
        parts = con.execute(
            f"select part_id, part_order, st_aswkb(st_geomfromtext(geom_wkt)) from {PARTS} "
            "where refused_because is null order by part_order"
        ).fetchall()
        cuts = con.execute(
            f"select cut_key, cut_order, cut_kind, line_part_id, other_part_id, end_side from {CUTS} order by cut_order"
        ).fetchall()
    except duckdb.CatalogException as missing:
        raise SystemExit(
            f"{PARTS} or {CUTS} is not in the warehouse: build it with dbt first (everything but "
            f"`source:derived+`), then run this step, then build `source:derived+`. ({missing})"
        ) from missing
    rows = [{"part_id": part_id, "part_order": order, "line": shapely.from_wkb(bytes(wkb))} for part_id, order, wkb in parts]
    if [row["part_order"] for row in rows] != list(range(len(rows))):
        raise SystemExit(f"{PARTS}'s part_order is not 0..{len(rows) - 1}: refusing to guess which part is which")
    keys = ("cut_key", "cut_order", "cut_kind", "line_part_id", "other_part_id", "end_side")
    return rows, [dict(zip(keys, cut)) for cut in cuts], build_trail_graph.ENDPOINT_SNAP_M


def cut_lines(parts: list[dict], cuts: list[dict], endpoint_snap_m: float) -> tuple[list[list], list[tuple[str, Point]], int]:
    """Every part's pieces, the landing of every joined end, and the crossing points' count.

    node_lines()' cutting, with its decisions read from `cuts` rather than
    re-derived: the same projection, the same intersection points (the lower
    part asked first, as node_lines() asks), the same landings, and
    _split_all itself."""
    to_projected, _ = build_trail_graph._transformers()
    lines = [transform(to_projected.transform, part["line"]) for part in parts]
    index = {part["part_id"]: position for position, part in enumerate(parts)}
    cut_points: list[list[Point]] = [[] for _ in lines]
    landings: list[tuple[str, Point]] = []
    crossings = 0
    for cut in cuts:
        line_index, other_index = index[cut["line_part_id"]], index[cut["other_part_id"]]
        line, other = lines[line_index], lines[other_index]
        if cut["cut_kind"] == "crossing":
            if not line.intersects(other):
                raise SystemExit(f"{cut['cut_key']}: the SQL says these parts cross and shapely says they do not")
            points = build_trail_graph._intersection_points(line.intersection(other))
            if points:
                crossings += len(points)
                cut_points[line_index].extend(points)
                cut_points[other_index].extend(points)
            continue
        if cut["cut_kind"] != "endpoint_join":
            raise SystemExit(f"{cut['cut_key']}: a cut of kind {cut['cut_kind']!r}, which this step does not make")
        endpoint = Point(line.coords[0] if cut["end_side"] == "start" else line.coords[-1])
        if line.intersects(other) or endpoint.distance(other) > endpoint_snap_m:
            raise SystemExit(f"{cut['cut_key']}: the SQL joins this end and shapely would not")
        landing = other.interpolate(other.project(endpoint))
        cut_points[other_index].append(landing)
        landings.append((cut["cut_key"], landing))
    return build_trail_graph._split_all(lines, cut_points), landings, crossings


def _geojson(geometry) -> str:
    """A LineString or Point as GeoJSON text, each coordinate the shortest text that reads back to the same double."""
    coordinates = shapely.get_coordinates(geometry).tolist()
    if geometry.geom_type == "Point":
        return json.dumps({"type": "Point", "coordinates": coordinates[0]})
    return json.dumps({"type": "LineString", "coordinates": coordinates})


def write_pieces(
    con: duckdb.DuckDBPyConnection,
    parts: list[dict],
    pieces: list[list],
    landings: list[tuple[str, Point]],
    loaded_at: datetime,
) -> tuple[int, int]:
    """Replace derived.graph_pieces with one row per piece and one per landing. Returns the two counts.

    A piece carries its place along its part and its place among all pieces
    (`piece_rank`), which is the order build_graph() walks them in."""
    rows = [
        ("piece", part["part_id"], piece_index, None, _geojson(piece))
        for part, part_pieces in zip(parts, pieces)
        for piece_index, piece in enumerate(part_pieces, start=1)
    ]
    rows = [(*row, rank) for rank, row in enumerate(rows)]
    rows += [("landing", None, None, cut_key, _geojson(landing), None) for cut_key, landing in landings]
    columns = list(zip(*rows)) if rows else [(), (), (), (), (), ()]

    def integers(values) -> tuple[np.ndarray, np.ndarray]:
        return (
            np.array([0 if value is None else value for value in values], dtype=np.int64),
            np.array([value is not None for value in values], dtype=bool),
        )

    piece_index, has_piece_index = integers(columns[2])
    piece_rank, has_piece_rank = integers(columns[5])
    con.register(
        "_graph_pieces_src",
        {
            "row_kind": np.array(columns[0], dtype=object),
            "part_id": np.array(columns[1], dtype=object),
            "piece_index": piece_index,
            "has_piece_index": has_piece_index,
            "piece_rank": piece_rank,
            "has_piece_rank": has_piece_rank,
            "cut_key": np.array(columns[3], dtype=object),
            "geometry": np.array(columns[4], dtype=object),
        },
    )
    try:
        con.execute(f"create schema if not exists {SCHEMA}")
        con.execute(f"""
            create or replace table {SCHEMA}.{TABLE} as
            select
                cast(row_kind as varchar) as row_kind,
                cast(part_id as varchar) as part_id,
                case when has_piece_index then cast(piece_index as integer) end as piece_index,
                case when has_piece_rank then cast(piece_rank as bigint) end as piece_rank,
                cast(cut_key as varchar) as cut_key,
                cast(geometry as varchar) as geometry,
                cast('{loaded_at.isoformat()}' as timestamptz) as _loaded_at
            from _graph_pieces_src
        """)
    finally:
        con.unregister("_graph_pieces_src")
    piece_count = sum(1 for row in rows if row[0] == "piece")
    return piece_count, len(rows) - piece_count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--warehouse", type=Path, default=WAREHOUSE_PATH)
    args = parser.parse_args(argv)

    with duckdb.connect(str(args.warehouse)) as con:
        con.execute("load spatial")
        parts, cuts, endpoint_snap_m = read_inputs(con)
        pieces, landings, crossings = cut_lines(parts, cuts, endpoint_snap_m)
        piece_count, landing_count = write_pieces(con, parts, pieces, landings, datetime.now(UTC))
    print(
        f"{SCHEMA}.{TABLE}: {len(parts):,} routable parts cut into {piece_count:,} pieces, "
        f"{crossings:,} crossing point(s), {landing_count:,} end(s) joined within {endpoint_snap_m:g} m"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
