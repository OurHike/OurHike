"""lib/trail_graph_route.py - the Python twin of the phone's router (#1290).

Every case here is one the client's own suite pins for trailGraph.ts, redone
on a hand-placed graph, because the module's whole claim is that it computes
what the phone will: the same partial-edge pricing, the same refusal of a
climb with a hole in it, the same direction swap on an edge walked backwards,
the same cut of a drawn line to the tapped fractions. A synthetic graph of a
few edges near (-74, 41) - never the real network (TESTING.md).
"""

from __future__ import annotations

import json

import pytest

from lib import trail_graph_route as router

LON, LAT = -74.0, 41.0
#: One degree of longitude at 41°N is ~84 km; 0.001° is ~84 m east-west.
STEP = 0.001


def node(x: int, y: int = 0) -> list:
    return [LON + x * STEP, LAT + y * STEP]


def graph_files(tmp_path, *, elevation=True, misaligned=False):
    """A chain 0-1-2-3 along one trail, a spur 1-4 on another, and a loop
    2-3 via node 5 on a third - every edge with a two-vertex geometry so the
    lengths the router prices are the lengths the lines draw."""
    nodes = [node(0), node(1), node(2), node(3), node(1, 1), node(2, 1)]
    edges = [
        {"from": 0, "to": 1, "trail_id": "t:pine", "source": "oprhp_trails", "name": "Pine Meadow Trail", "blaze_color": "Red"},
        {"from": 1, "to": 2, "trail_id": "t:pine", "source": "oprhp_trails", "name": "Pine Meadow Trail", "blaze_color": "Red"},
        {"from": 2, "to": 3, "trail_id": "t:pine", "source": "oprhp_trails", "name": "Pine Meadow Trail", "blaze_color": "Red"},
        {"from": 1, "to": 4, "trail_id": "t:spur", "source": "oprhp_trails", "name": "Spur Trail", "blaze_color": "Blue"},
        {"from": 2, "to": 5, "trail_id": "t:loop", "source": "nynjtc_long_path", "name": "Ridge Loop", "blaze_color": "Yellow"},
        {"from": 5, "to": 3, "trail_id": "t:loop", "source": "nynjtc_long_path", "name": "Ridge Loop", "blaze_color": "Yellow"},
    ]
    geometry = [[nodes[e["from"]], nodes[e["to"]]] for e in edges]
    for edge, line in zip(edges, geometry):
        edge["length_m"] = router.metres_between(tuple(line[0]), tuple(line[1]))
    climbs = [[10, 0], [20, 0], [30, 0], [5, 5], [40, 10], [10, 40]]
    (tmp_path / "trail_graph.json").write_text(json.dumps({"nodes": nodes, "edges": edges}))
    (tmp_path / "trail_graph_geometry.json").write_text(json.dumps(geometry))
    if elevation:
        (tmp_path / "trail_graph_elevation.json").write_text(json.dumps(climbs[:-1] if misaligned else climbs))
    return tmp_path


@pytest.fixture
def graph(tmp_path):
    root = graph_files(tmp_path)
    return router.load_graph(root / "trail_graph.json", root / "trail_graph_geometry.json", root / "trail_graph_elevation.json")


def point(graph, x: float, y: float = 0.0, **kwargs) -> router.GraphPoint:
    found = router.nearest_point(graph, LON + x * STEP, LAT + y * STEP, **kwargs)
    assert found is not None
    return found


class TestSnapping:
    def test_a_point_beside_a_line_lands_on_it_with_its_fraction(self, graph):
        snapped = point(graph, 0.25, 0.0001)

        assert snapped.edge_index == 0
        assert abs(snapped.fraction - 0.25) < 0.01
        assert snapped.off_metres < 12
        assert abs(snapped.at[1] - LAT) < 1e-9

    def test_a_point_too_far_from_any_line_is_refused_at_the_phones_radius(self, graph):
        """MAX_OFF_NETWORK_FEET is 150 ft; 0.002° of latitude is ~222 m."""
        assert router.nearest_point(graph, LON + 0.5 * STEP, LAT - 2 * STEP) is None


class TestRouting:
    def test_a_walk_along_one_trail_prices_the_partial_ends_by_fraction(self, graph):
        route = router.route_between(graph, point(graph, 0.5), point(graph, 2.5))

        assert route is not None
        assert route.edge_indices == [0, 1, 2]
        expected = 0.5 * graph.edges[0]["length_m"] + graph.edges[1]["length_m"] + 0.5 * graph.edges[2]["length_m"]
        assert abs(route.metres - expected) < 0.01
        assert [leg.name for leg in route.legs] == ["Pine Meadow Trail"]
        assert abs(route.legs[0].miles - route.miles) < 1e-9

    def test_a_walk_on_one_edge_needs_no_search(self, graph):
        route = router.route_between(graph, point(graph, 0.2), point(graph, 0.7))

        assert route.edge_indices == [0]
        assert abs(route.metres - 0.5 * graph.edges[0]["length_m"]) < 0.01

    def test_legs_change_where_the_trail_changes(self, graph):
        route = router.route_between(graph, point(graph, 0.5), point(graph, 1, 0.5))

        assert route.edge_indices == [0, 3]
        assert [(leg.name, leg.blaze_color) for leg in route.legs] == [("Pine Meadow Trail", "Red"), ("Spur Trail", "Blue")]

    def test_the_shortest_of_two_ways_round_is_taken(self, graph):
        """Node 2 to node 3 directly (one edge) beats the loop via node 5."""
        route = router.route_between(graph, point(graph, 1.5), point(graph, 2.9))

        assert route.edge_indices == [1, 2]

    def test_a_loop_closes_back_to_its_first_point(self, graph):
        loop = router.close_the_loop(graph, [point(graph, 2.1), point(graph, 2, 0.9), point(graph, 2.9)])

        assert loop is not None
        assert loop.sections[-1].end.edge_index == loop.sections[0].start.edge_index
        assert [leg.name for leg in loop.legs] == ["Pine Meadow Trail", "Ridge Loop", "Pine Meadow Trail"]

    def test_an_unroutable_leg_refuses_the_whole_walk(self, graph):
        """An island edge: nothing connects to it, so no walk reaches it."""
        graph.edges.append(
            {
                "from": 6,
                "to": 7,
                "trail_id": "t:island",
                "source": "x",
                "name": "Island",
                "blaze_color": "None",
                "length_m": 100.0,
            }
        )
        graph.nodes.extend([node(10), node(11)])
        graph.geometry.append([node(10), node(11)])
        graph.climb.append([0, 0])
        graph.adjacency.setdefault(6, []).append((7, 6))
        graph.adjacency.setdefault(7, []).append((6, 6))
        island = router.GraphPoint(edge_index=6, fraction=0.5, at=(LON + 10.5 * STEP, LAT), off_metres=0.0)

        assert router.route_between(graph, point(graph, 0.5), island) is None
        assert router.route_through(graph, [point(graph, 0.5), point(graph, 1.5), island]) is None


class TestClimb:
    def test_climb_is_pro_rated_on_partial_edges_and_summed_across_the_rest(self, graph):
        route = router.route_between(graph, point(graph, 0.5), point(graph, 2.5))

        gain, loss = route.climb
        assert abs(gain - (5 + 20 + 15)) < 0.01
        assert loss == 0

    def test_walking_an_edge_backwards_swaps_its_ascent_for_its_descent(self, graph):
        forward = router.route_between(graph, point(graph, 0.0), point(graph, 2.0))
        backward = router.route_between(graph, point(graph, 2.0), point(graph, 0.0))

        assert forward.climb == pytest.approx((30, 0))
        assert backward.climb == pytest.approx((0, 30))

    def test_a_closed_loop_climbs_exactly_what_it_descends(self, graph):
        loop = router.close_the_loop(graph, [point(graph, 0.0), point(graph, 2, 0.9)])

        gain, loss = loop.climb
        assert abs(gain - loss) < 0.01

    def test_a_missing_edge_climb_makes_the_walk_unpriced_not_a_partial_total(self, graph):
        graph.climb[1] = None
        route = router.route_between(graph, point(graph, 0.5), point(graph, 2.5))

        assert route.climb is None
        assert route.climb_note
        assert route.miles > 0

    def test_a_misaligned_sidecar_prices_nothing_and_says_why(self, tmp_path):
        """The production defect measured 2026-09-09: a climb file built
        against a different graph. Pairing by index would attribute one
        edge's climb to another; refusing is the honest answer."""
        root = graph_files(tmp_path, misaligned=True)
        graph = router.load_graph(
            root / "trail_graph.json", root / "trail_graph_geometry.json", root / "trail_graph_elevation.json"
        )

        assert graph.climb is None
        assert "5 rows against 6 edges" in graph.climb_note
        route = router.route_between(graph, point(graph, 0.5), point(graph, 2.5))
        assert route.climb is None
        assert "different graph" in route.climb_note

    def test_no_sidecar_is_no_climb(self, tmp_path):
        root = graph_files(tmp_path, elevation=False)
        graph = router.load_graph(
            root / "trail_graph.json", root / "trail_graph_geometry.json", root / "trail_graph_elevation.json"
        )

        assert graph.climb is None
        assert router.route_between(graph, point(graph, 0.5), point(graph, 2.5)).climb is None


class TestDrawing:
    def test_the_drawn_line_is_cut_to_the_walked_fractions(self, graph):
        route = router.route_between(graph, point(graph, 0.5), point(graph, 2.5))
        lines = router.route_lines(graph, route)

        assert len(lines) == 3
        assert abs(lines[0][0][0] - (LON + 0.5 * STEP)) < 1e-6
        assert abs(lines[-1][-1][0] - (LON + 2.5 * STEP)) < 1e-6

    def test_an_edge_walked_backwards_is_drawn_backwards(self, graph):
        route = router.route_between(graph, point(graph, 2.0), point(graph, 0.0))
        lines = router.route_lines(graph, route)

        assert lines[0][0][0] > lines[0][-1][0]

    def test_a_re_walked_leg_is_drawn_again_over_itself(self, graph):
        out_and_back = router.route_through(graph, [point(graph, 0.2), point(graph, 0.8), point(graph, 0.2)])
        lines = router.route_lines(graph, out_and_back)

        assert len(lines) == 2
        assert abs(out_and_back.metres - 1.2 * graph.edges[0]["length_m"]) < 0.01

    def test_a_walk_without_geometry_is_not_drawn_as_chords(self, tmp_path):
        root = graph_files(tmp_path)
        graph = router.load_graph(root / "trail_graph.json")
        route = router.route_between(graph, point(graph, 0.5), point(graph, 2.5))

        assert route is not None
        assert router.route_lines(graph, route) is None

    def test_a_geometry_sidecar_of_the_wrong_length_is_refused(self, tmp_path):
        root = graph_files(tmp_path)
        (root / "trail_graph_geometry.json").write_text(json.dumps([[node(0), node(1)]]))

        with pytest.raises(ValueError, match="refusing to guess the pairing"):
            router.load_graph(root / "trail_graph.json", root / "trail_graph_geometry.json")


class TestJunctions:
    def test_where_two_named_trails_meet(self, graph):
        found = router.junctions_of(graph, "pine meadow", "spur", (LON + STEP, LAT))

        assert [n for n, _ in found] == [1]

    def test_a_point_at_a_node_routes_from_it(self, graph):
        at_node = router.point_at_node(graph, 4)
        route = router.route_between(graph, at_node, point(graph, 0.0))

        assert route.edge_indices == [3, 0]
        assert abs(route.metres - (graph.edges[3]["length_m"] + graph.edges[0]["length_m"])) < 0.01


def test_keep_near_drops_geometry_far_from_the_points_but_keeps_the_graph_whole(tmp_path):
    root = graph_files(tmp_path)
    graph = router.load_graph(
        root / "trail_graph.json", root / "trail_graph_geometry.json", keep_near=[(LON, LAT)], keep_radius_m=50
    )

    assert len(graph.edges) == 6
    assert graph.has_geometry(0)
    assert not graph.has_geometry(5)
