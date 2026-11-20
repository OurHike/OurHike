"""lib/topojson.py against the TopoJSON specification's own rules (#1965).

topojson-specification §2.1.2 (quantized arcs are delta-encoded) and §2.2.4
(a negative arc index is the one's complement of a reversed arc) are the two
rules a hand-written reader most easily gets wrong, and each has a case here.
"""

from __future__ import annotations

from lib import topojson

#: Two unit squares side by side sharing one edge (arc 0), and a third far
#: away. Unquantized, so the positions are the arcs' own.
SQUARES = {
    "type": "Topology",
    "arcs": [
        [[1.0, 0.0], [1.0, 1.0]],
        [[1.0, 1.0], [0.0, 1.0], [0.0, 0.0], [1.0, 0.0]],
        [[1.0, 0.0], [2.0, 0.0], [2.0, 1.0], [1.0, 1.0]],
        [[10.0, 10.0], [11.0, 10.0], [11.0, 11.0], [10.0, 10.0]],
    ],
    "objects": {
        "shapes": {
            "type": "GeometryCollection",
            "geometries": [
                {"type": "Polygon", "id": "west", "properties": {"name": "West"}, "arcs": [[1, 0]]},
                {"type": "Polygon", "id": "east", "arcs": [[2, -1]]},
                {"type": "Polygon", "id": 7, "arcs": [[3]]},
                {"type": None, "id": "empty"},
            ],
        }
    },
}


def test_quantized_arcs_are_deltas_from_the_position_before():
    topology = {
        "type": "Topology",
        "transform": {"scale": [0.5, 2.0], "translate": [100.0, -10.0]},
        "arcs": [[[2, 1], [2, 0], [0, 3], [-4, -4]]],
        "objects": {},
    }
    assert topojson.decode_arcs(topology) == [[(101.0, -8.0), (102.0, -8.0), (102.0, -2.0), (100.0, -10.0)]]


def test_a_negative_index_walks_its_arc_backwards_and_junctions_are_not_repeated():
    arcs = topojson.decode_arcs(SQUARES)
    assert topojson.stitch([2, -1], arcs) == [(1.0, 0.0), (2.0, 0.0), (2.0, 1.0), (1.0, 1.0), (1.0, 0.0)]
    assert topojson.arc_index(-1) == 0 and topojson.arc_index(-3) == 2


def test_features_build_each_polygon_skip_empty_members_and_keep_ids_as_text():
    features = topojson.features(SQUARES, "shapes")
    assert [f.id for f in features] == ["west", "east", "7"]
    assert features[0].properties == {"name": "West"}
    assert features[0].geometry.area == 1.0 and features[1].geometry.area == 1.0
    assert features[1].arc_indexes == frozenset({0, 2})


def test_only_the_arcs_two_members_share_are_borders():
    arcs = topojson.decode_arcs(SQUARES)
    features = topojson.features(SQUARES, "shapes", arcs)
    assert topojson.shared_arcs(features, arcs) == [[(1.0, 0.0), (1.0, 1.0)]]
    assert topojson.shared_arcs(features[:1], arcs) == []
