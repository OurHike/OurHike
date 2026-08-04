"""Tests for lib/poly.py - Osmosis .poly serialization and the padded clip
shape. The serialization tests parse the text back rather than asserting on
exact strings, because the format's meaning is the coordinates, not the
whitespace; the osmium test then feeds a generated .poly to the real consumer
(skipped where osmium-tool isn't installed - CI installs it, and the format
tests still hold everywhere)."""

import shutil
import subprocess

import pytest
from shapely.geometry import MultiPolygon, Point, Polygon, box

from lib.poly import clip_shape, to_poly


def parse_poly(text: str):
    """(name, [(section_name, [(x, y), ...]), ...]) - a minimal reader for
    the format to_poly writes, so assertions speak coordinates."""
    lines = text.strip().splitlines()
    name, body = lines[0], lines[1:]
    assert body[-1] == "END"
    sections = []
    current = None
    for line in body[:-1]:
        if line == "END":
            sections.append(current)
            current = None
        elif current is None:
            current = (line, [])
        else:
            x, y = line.split()
            current[1].append((float(x), float(y)))
    assert current is None, "unterminated section"
    return name, sections


def test_a_square_round_trips_through_the_format():
    name, sections = parse_poly(to_poly(box(-74.1, 41.0, -73.9, 41.2), name="test-area"))
    assert name == "test-area"
    assert len(sections) == 1
    _, coords = sections[0]
    # Shapely closes rings; the format keeps that closure.
    assert coords[0] == coords[-1]
    assert set(coords) == {(-74.1, 41.0), (-73.9, 41.0), (-73.9, 41.2), (-74.1, 41.2)}


def test_a_hole_becomes_a_bang_prefixed_section():
    outer = box(0, 0, 10, 10)
    hole = box(4, 4, 6, 6)
    ring = Polygon(outer.exterior.coords, [hole.exterior.coords])
    _, sections = parse_poly(to_poly(ring))
    assert [s[0] for s in sections] == ["1", "!2"]
    assert set(sections[1][1]) == {(4.0, 4.0), (6.0, 4.0), (6.0, 6.0), (4.0, 6.0)}


def test_a_multipolygon_gets_one_section_per_part():
    parts = MultiPolygon([box(0, 0, 1, 1), box(5, 5, 6, 6)])
    _, sections = parse_poly(to_poly(parts))
    assert [s[0] for s in sections] == ["1", "2"]


def test_non_polygonal_geometry_is_rejected():
    with pytest.raises(ValueError, match="Point"):
        to_poly(Point(0, 0))


def test_clip_shape_always_covers_the_original():
    # A deliberately jagged shape: buffer of a point ring, so simplification
    # has real vertices to remove. The guarantee under test is the docstring's
    # superset argument - simplify moves the boundary at most `tolerance`, and
    # buffering by the same tolerance restores coverage.
    jagged = Point(0, 0).buffer(1.0, quad_segs=64).union(Point(1.5, 0).buffer(0.8, quad_segs=64))
    clipped = clip_shape(jagged, tolerance_deg=0.05)
    assert clipped.covers(jagged)
    assert len(clipped.exterior.coords) < len(jagged.exterior.coords)


def test_clip_shape_output_serializes():
    # The two halves compose: whatever clip_shape emits, to_poly must accept -
    # including a MultiPolygon from disjoint corridor pieces.
    disjoint = Point(0, 0).buffer(1).union(Point(10, 10).buffer(1))
    text = to_poly(clip_shape(disjoint))
    assert text.count("END") >= 3


@pytest.mark.skipif(shutil.which("osmium") is None, reason="osmium-tool not installed (CI installs it)")
def test_osmium_accepts_the_generated_poly_and_clips_with_it(tmp_path):
    """The real consumer: osmium extract with a to_poly file keeps what is
    inside the shape and drops what is outside. This is the test that would
    catch a format drift no round-trip through our own parser can."""
    osm_xml = tmp_path / "in.osm"
    osm_xml.write_text(
        """<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6" generator="test">
  <node id="1" version="1" lat="41.05" lon="-74.05"/>
  <node id="2" version="1" lat="41.06" lon="-74.04"/>
  <node id="3" version="1" lat="45.00" lon="-100.00"/>
  <way id="10" version="1">
    <nd ref="1"/>
    <nd ref="2"/>
    <tag k="highway" v="path"/>
  </way>
</osm>
"""
    )
    poly_path = tmp_path / "clip.poly"
    poly_path.write_text(to_poly(box(-74.1, 41.0, -73.9, 41.2), name="clip"))
    out = tmp_path / "out.osm.pbf"

    subprocess.run(
        ["osmium", "extract", "--polygon", str(poly_path), "--overwrite", "-o", str(out), str(osm_xml)],
        check=True,
        capture_output=True,
    )

    kept = subprocess.run(["osmium", "cat", str(out), "-f", "osm"], check=True, capture_output=True, text=True).stdout
    assert 'id="1"' in kept and 'id="2"' in kept, "nodes inside the shape must survive the clip"
    assert 'id="3"' not in kept, "a node far outside the shape must be clipped away"
