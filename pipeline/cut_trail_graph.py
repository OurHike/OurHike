"""Cut the junction graph into 1-degree coverage cells (#1257 stage 3).

THE FILE THIS CUTS OUTGREW A PHONE. build_trail_graph.py writes the whole
network's topology as one `trail_graph.json` and its edges' vertices as one
index-aligned `trail_graph_geometry.json`; export_network_elevation.py and
export_network_profile.py add two more index-aligned companions. On 2026-09-07
the graph was promoted at 78,595,556 bytes (nationwide USFS trails, #1231):
`JSON.parse` plus the adjacency build held a phone's main thread for 9.8 s,
which was "the app is hanging on the first page" (#1254), and the geometry was
224,102,405 bytes on top. The client now declines anything over 32 MiB
(client/src/lib/artifactBudget.ts), so until this cut a phone had no day hikes
at all. The maintainer's call is that the data stays and the delivery shape
changes: a phone loads the cells under the hike it is planning and nothing
else.

WHAT A CELL HOLDS, AND THE TWO RULES THAT DECIDE IT

The same whole-degree graticule squares cut_cells.py cuts the basemap and the
network tiles into (lib/corridor_grid.graticule_cells, cell_name), so the three
families of cells describe the same ground and the client's one index reader
(lib/coverageCells.ts) reads all of them.

1. AN EDGE IS NEVER CUT. It goes whole into every cell its own bounding box
   touches once widened by the seam margin - cut_cells.py's routing rule with
   the edge's box standing in for the tile's. Splitting an edge at a seam
   would invent a node the ground does not have (the failure the builder's
   own rounding is written to avoid: build_trail_graph.py rounds toward
   disconnection, never toward a junction) and would break every companion,
   because a `[gain, loss]` measured along a whole edge does not divide. So
   a long edge lands in several cells, and that is duplication measured in
   bytes rather than a wrong route: measured on 2026-09-07's graph, 2,221 of
   466,966 edges (0.5%) cross a seam by their own extent, and with the 3 km
   margin the 503 cells hold 530,207 placements, 13.5% more than the edges.

2. IDENTITY IS GLOBAL, POSITIONS ARE LOCAL. In the whole graph a node is its
   position in `nodes` and an edge is its position in `edges` - there is no
   other id, and every companion is aligned by that position. A shard keeps
   both facts explicit: `node_ids` and `edge_ids` carry each row's position in
   the whole graph, while `from`/`to` index the shard's own `nodes`, so a
   shard on its own is a complete graph (client/src/lib/trailGraph.ts's
   buildGraphIndex reads it unchanged) and two shards loaded together agree
   on which node is which without re-matching coordinates - a second
   implementation of build_trail_graph._node_id on the phone would be a
   second place to get "the same place" wrong. The companions are cut per
   shard in the shard's own edge order, so the client's existing rule "refuse
   a companion whose length disagrees with the edges" holds per cell.

WHAT IS PUBLISHED. Per cell `trail_graph_cell_<name>.json` and
`trail_graph_geometry_cell_<name>.json`, plus `trail_graph_elevation_cell_
<name>.json` and `trail_graph_profile_cell_<name>.json` when the whole
companions exist AND align with the graph (a companion left from an earlier
graph is refused loudly rather than cut against the wrong edges - the two
exporters make the same refusal); the index `trail_graph_cells.json` in the
other families' schema, with `context: null` and `context_zoom: 0` because a
graph has no zoom and no shared context; and `trail_graph_cells_manifest.json`
for publish.py, which collects it inside the graph's own `reaches_hikers` gate
(the same stewards' data, one decision). The whole files stay published as the
cut's input and for older clients; the current client asks for none of them.

Measured by running this on 2026-09-07's production graph (466,966 edges,
316,492 nodes, 78,595,556 bytes with 224,102,405 of geometry): 29.9 s to cut
into 502 cells of 3,740 candidates, 530,190 placements (13.5% seam
duplication at 3 km). The densest shard, n44w072 in Vermont and New
Hampshire, is 12,663,031 bytes of graph and 6,954,151 of geometry; the median
is 28,406 and 220,210; Harriman's n41w075 is 9,754 edges, 1,791,818 bytes of
graph and 2,290,941 of geometry; the index is 166,721 bytes. Every shard is
inside the 32 MiB budget that declines the whole. That day's companions were
not cut: the bucket's elevation file had 42,103 entries against the graph's
466,966 edges, written before the graph grew, and the refusal below is what
kept them off every cell.

    .venv/Scripts/python cut_trail_graph.py
"""

import argparse
import json
from pathlib import Path

from cut_cells import PROCESSED_DIR, SEAM_MARGIN_KM, GraticuleLookup, cell_name
from export_elevation import sha256_file
from lib.corridor_grid import CELL_DEGREES, graticule_cells

FAMILY = "trail_graph"

GRAPH_NAME = "trail_graph.json"
GEOMETRY_NAME = "trail_graph_geometry.json"
ELEVATION_NAME = "trail_graph_elevation.json"
PROFILE_NAME = "trail_graph_profile.json"
GRAPH_MANIFEST_NAME = "trail_graph_manifest.json"

# The four halves of one cell, named for the whole file each is cut from with
# the cell's name between the stem and the extension - so the family reads as
# a family in the bucket, and lib/r2_keys.py's rules pass unchanged.
# client/src/lib/config.ts's trailGraphCellKey spells the same four, and
# tests/test_cut_trail_graph.py reads that file to hold them equal.
HALVES = ("graph", "geometry", "elevation", "profile")
CELL_KEY_PATTERNS = {
    "graph": "trail_graph_cell_{name}.json",
    "geometry": "trail_graph_geometry_cell_{name}.json",
    "elevation": "trail_graph_elevation_cell_{name}.json",
    "profile": "trail_graph_profile_cell_{name}.json",
}
INDEX_NAME = f"{FAMILY}_cells.json"
MANIFEST_NAME = f"{FAMILY}_cells_manifest.json"


def cell_key(name: str, half: str) -> str:
    """The bucket key of one half of one cell."""
    return CELL_KEY_PATTERNS[half].format(name=name)


def edge_bounds(vertices: list, nodes: list, edge: dict) -> tuple[float, float, float, float]:
    """An edge's bounding box in lon/lat - its vertices' where it has any,
    its two nodes' otherwise (a degenerate geometry must still be filed
    somewhere, and its nodes are somewhere)."""
    points = vertices if len(vertices) >= 2 else [nodes[edge["from"]], nodes[edge["to"]]]
    lons = [p[0] for p in points]
    lats = [p[1] for p in points]
    return min(lons), min(lats), max(lons), max(lats)


def _aligned_companion(in_dir: Path, name: str, edge_count: int) -> list | None:
    """The whole companion, or None when it is absent or was written against a
    different graph - refused rather than cut against the wrong edges, which
    is export_network_elevation.py's own refusal one step later."""
    path = in_dir / name
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if len(data) != edge_count:
        print(
            f"WARNING: {name} has {len(data):,} entries against {edge_count:,} edges - "
            "written for an earlier graph, so it is NOT cut; the cells carry no such companion"
        )
        return None
    return data


def cut_trail_graph(
    in_dir: Path = PROCESSED_DIR,
    out_dir: Path = PROCESSED_DIR,
    margin_km: float = SEAM_MARGIN_KM,
) -> dict:
    """Cut the whole graph in `in_dir` into per-cell shards in `out_dir`,
    write the index and publish.py's manifest, and return the manifest."""
    graph = json.loads((in_dir / GRAPH_NAME).read_text(encoding="utf-8"))
    geometry = json.loads((in_dir / GEOMETRY_NAME).read_text(encoding="utf-8"))
    nodes, edges = graph["nodes"], graph["edges"]
    if len(geometry) != len(edges):
        raise SystemExit(
            f"{GEOMETRY_NAME} has {len(geometry):,} entries against {len(edges):,} edges - "
            "refusing to guess the pairing (the same refusal export_network_elevation.py makes)"
        )
    if not edges:
        raise SystemExit(f"{GRAPH_NAME} holds no edges: nothing to cut, and an empty family would read as coverage")

    companions = {
        half: data
        for half, name in (("elevation", ELEVATION_NAME), ("profile", PROFILE_NAME))
        if (data := _aligned_companion(in_dir, name, len(edges))) is not None
    }

    graph_manifest_path = in_dir / GRAPH_MANIFEST_NAME
    sources = {}
    if graph_manifest_path.exists():
        sources = json.loads(graph_manifest_path.read_text(encoding="utf-8")).get("sources", {})

    # CANDIDATES from the nodes' own extent, decided by the edges: a cell no
    # edge's widened box touches is ground with no trail and is not built.
    lons = [n[0] for n in nodes]
    lats = [n[1] for n in nodes]
    candidates = graticule_cells((min(lons), min(lats), max(lons), max(lats)))
    lookup = GraticuleLookup(candidates)

    routing: dict[int, list[int]] = {}
    placements = 0
    for edge_index, (edge, vertices) in enumerate(zip(edges, geometry, strict=True)):
        for cell_index in lookup.hits(edge_bounds(vertices, nodes, edge), margin_km):
            routing.setdefault(cell_index, []).append(edge_index)
            placements += 1

    out_dir.mkdir(parents=True, exist_ok=True)
    artifact_names: list[str] = []
    index_cells = []
    for cell_index in sorted(routing):
        west, south, east, north = candidates[cell_index]
        name = cell_name(west, south)
        edge_indices = routing[cell_index]
        node_ids = sorted({edges[i]["from"] for i in edge_indices} | {edges[i]["to"] for i in edge_indices})
        local = {node_id: position for position, node_id in enumerate(node_ids)}
        shard = {
            "nodes": [nodes[node_id] for node_id in node_ids],
            "node_ids": node_ids,
            "edges": [{**edges[i], "from": local[edges[i]["from"]], "to": local[edges[i]["to"]]} for i in edge_indices],
            "edge_ids": edge_indices,
        }
        halves = {
            "graph": shard,
            "geometry": [geometry[i] for i in edge_indices],
            **{half: [data[i] for i in edge_indices] for half, data in companions.items()},
        }
        keys = {}
        for half, payload in halves.items():
            key = cell_key(name, half)
            (out_dir / key).write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
            artifact_names.append(key)
            keys[half] = key
        index_cells.append(
            {
                "name": name,
                "key": keys["graph"],
                "bounds": [round(v, 6) for v in (west, south, east, north)],
                "edges": len(edge_indices),
                # The other halves, named so a client need not derive them -
                # and null where the run cut none, which is what "no figures"
                # for a cell looks like from the index.
                "companions": {half: keys.get(half) for half in HALVES if half != "graph"},
            }
        )

    # The other families' index schema (cut_cells.py), so lib/coverageCells.ts
    # reads it with the same parser and verify_release.py's check 20 walks it
    # with the same code. `context_zoom` is 0 and `context` null because a graph
    # has no zoom to share below and nothing shared at all.
    index = {
        "cell_degrees": CELL_DEGREES,
        "seam_margin_km": margin_km,
        "context_zoom": 0,
        "context": None,
        "cells": index_cells,
    }
    (out_dir / INDEX_NAME).write_text(json.dumps(index, indent=2), encoding="utf-8")
    artifact_names.insert(0, INDEX_NAME)

    duplication_pct = (placements - len(edges)) / len(edges) * 100
    sizes = {name: (out_dir / name).stat().st_size for name in artifact_names}
    graph_shards = [sizes[c["key"]] for c in index_cells]
    manifest = {
        "artifacts": {
            name: {"path": str(out_dir / name), "sha256": sha256_file(out_dir / name), "size_bytes": sizes[name]}
            for name in artifact_names
        },
        "stats": {
            "cells": len(index_cells),
            "candidate_cells": len(candidates),
            "edges": len(edges),
            "edge_placements": placements,
            "seam_duplication_pct": round(duplication_pct, 2),
            "companions_cut": sorted(companions),
            "largest_graph_shard_bytes": max(graph_shards),
            "median_graph_shard_bytes": sorted(graph_shards)[len(graph_shards) // 2],
        },
        # The licence gate travels with the derivation, as build_trail_graph.py
        # carries it: publish.py collects this manifest inside the graph's own
        # reaches_hikers branch, and this copy says whose data the cells are.
        "sources": sources,
    }
    (out_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    stats = manifest["stats"]
    print(
        f"{FAMILY}: {stats['edges']:,} edges -> {stats['edge_placements']:,} placements across {stats['cells']} cells "
        f"(of {stats['candidate_cells']} the nodes' extent covers), {stats['seam_duplication_pct']:.1f}% seam "
        f"duplication at {margin_km} km; companions cut: {', '.join(stats['companions_cut']) or 'none'}; "
        f"largest shard {stats['largest_graph_shard_bytes']:,} bytes, median {stats['median_graph_shard_bytes']:,}."
    )
    print(f"{len(artifact_names)} artifacts -> {out_dir}, manifest -> {out_dir / MANIFEST_NAME}")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--margin-km", type=float, default=SEAM_MARGIN_KM)
    args = parser.parse_args()
    cut_trail_graph(margin_km=args.margin_km)
