# Ordering the centerline pieces

What `export_elevation.py` does to put ATC's centerline in trail order, what
the source geometry actually looks like, which fixes failed, and the one that
closed it.

**Closed by marker calibration (#652 — The elevation profile's mile axis is
out of order in 18 places, by up to 46 miles).** The graph-walking measurements
below are kept as the record of why the obvious fixes do not work; the fix that
does is at the bottom, and `calibrate_parts_to_markers()` in
`export_elevation.py` is its implementation. #559 was independently fixed by
marking the seams — see that module's docstring point 4 — and that fix stays
correct regardless of ordering.

## What the straight-axis sort did, and what it cost

`ordered_oriented_parts()` reverses any piece whose own coordinates run
north-to-south, then sorts every piece by its start point's
`_trail_axis_projection` — the projection onto a straight Springer→Katahdin
line. It survives as the pre-calibration pass (it still supplies the
orientation for pieces too small for the markers to orient), but nothing
downstream reads a mile off its order any more.

## What that cost, measured

Against the live ATC centerline, 2026-08-13:

| | |
|---|---|
| pieces after `ST_LineMerge` | 558 |
| their total length | 2,162.6 mi |
| junctions between them | 557 |
| **median junction gap** | **0 ft** |
| junctions over 0.1 mi | 143 |
| junctions over 10 mi | 18 |
| total gap | 674.7 mi |
| largest single jump | 46.5 mi |

Two of those settle what kind of problem it is. **The median gap is exactly
zero** — 414 of 557 junctions join perfectly — and **the pieces already add up
to the whole trail**, 2,162.6 mi against roughly 2,197. So a 46.5-mile "gap" is
not missing trail. It is the sort leaping 46 miles away and coming back.

## What the source geometry actually is

Union-find over piece endpoints coinciding within 1 m:

```
558 pieces  ->  6 connected components
  774.4 mi (175 pieces)
  680.1 mi (139 pieces)
  501.0 mi (133 pieces)
  105.3 mi ( 64 pieces)
  101.8 mi ( 46 pieces)
    0.0 mi (  1 piece — degenerate, zero length)
```

**ATC's centerline has five genuine discontinuities, not 557.** The 143 bad
junctions are almost entirely the straight-line sort interleaving pieces from
the 774-mile chain with pieces from the 680-mile chain and back again.

Which sounds like the fix is easy, and then the node degrees say otherwise —
counting how many piece-ends meet at each point:

```
degree 1  ->  15 nodes    (chain ends)
degree 2  -> 403 nodes    (ordinary joins)
degree 4  ->   1 node
degree 5  ->   3 nodes
degree 6  ->  44 nodes
degree 12 ->   1 node
```

**Forty-eight nodes have four or more piece-ends coinciding; one has twelve.**
A trail does not branch six ways. That is duplicate or overlapping geometry
surviving the merge — 3,025 raw features collapsing to 558 pieces leaves room
for it — and it means a component cannot be walked as a chain until something
decides what happens at those nodes.

## What has been tried, and how it failed

| approach | total gap | largest jump | junctions > 0.1 mi |
|---|---:|---:|---:|
| current straight-axis sort | 674.7 mi | 46.5 mi | 143 |
| greedy nearest-endpoint chain | 1,133.4 mi | **474.3 mi** | **24** |
| component walk from a degree-1 end | 2,176.2 mi | 473.8 mi | — |

**Greedy nearest-endpoint** connects 534 of 557 junctions essentially perfectly
— a large improvement on the count — and then paints itself into a corner and
leaps 474 miles back to pick up what it skipped. That is the classic greedy
failure and it makes the total distance worse than what we have.

**Walking each component from a degree-1 end** does worse still: the walk
wanders at the degree-6 nodes, leaves most of the component unreached, and the
unreached pieces get appended arbitrarily.

Neither was a serious attempt and neither should be read as proving the problem
unsolvable. They are recorded because both look obviously correct before you
run them.

## The fix that worked: calibrate to ATC's own miles, not to the graph

The graph problem above never needed solving, because the source data carries
a trail-sequence field after all — just not on the centerline.
`half_mile_points_from_springer` is 4,395 points, each stamped with ATC's own
NOBO mile in `Measure`, and they sit **on** the centerline: measured
2026-08-18, the p99 marker→nearest-piece distance is 0.0 m and the maximum is
3.4 m. `calibrate_parts_to_markers()` snaps each marker to its piece and then
uses them for everything the projection was guessing at:

- **Order** comes from each piece's marker miles (the straight-axis sort had
  143 junctions over 0.1 mi; the markers put every piece where ATC says it
  is).
- **Orientation** comes from whether `Measure` rises or falls along the
  piece — which caught 33 pieces the axis heuristic had backwards, the AT's
  real north-south switchbacks.
- **Scale** comes from piecewise-linear interpolation through the markers, so
  `distance_mi` *is* ATC's mile — the same scale closures'
  `start_mile_marker` and ATC's updates quote. Between markers the piece's
  own geometry carries the distance; past a piece's end markers it
  extrapolates at unit slope.
- **Duplicate geometry** (the degree-6 nodes) stops being a walking hazard
  and becomes measurable: overlapping pieces land on overlapping mile ranges,
  and `build_profile` publishes each mile once (~5 mi clipped on the real
  data) instead of twice.

Accuracy, measured honestly — each piece calibrated from its even-indexed
markers, scored on the odd-indexed ones it never saw:

| | uncalibrated axis (2026-08-18) | calibrated, held-out |
|---|---:|---:|
| median \|axis − Measure\| | 7.7 mi | **0.003 mi** |
| p95 | 30.9 mi | 0.055 mi |
| max | 101.8 mi | 0.497 mi |
| within 0.5 mi of ATC | 2.5% | 100% |

`measure_marker_agreement()` re-runs that holdout on every export and
`require_marker_agreement()` refuses to publish if it drifts past thresholds
set with 4–15x headroom over those figures — a quietly-degraded calibration
would be worse than the fault it fixed, because this time the code claims to
be calibrated. Pieces no marker snapped to (182 of 558, totalling 7.5 mi,
none over 0.43 mi) are anchored from the nearest marker, bounding their error
by the marker spacing plus their own length.

## Reproducing any of this

Fetch the centerline (`lib/arcgis.fetch_layer_to_file` off `sources.json`),
then in DuckDB with `spatial`, reusing the module's own functions:

```python
parts = reproject_lines_to_meters(con, ordered_oriented_parts(load_merged_trail_line(con, CENTERLINE_PATH)))
```

Everything above is arithmetic on `parts` — endpoint distances for the gaps,
union-find over endpoints rounded to 1 m for the components, a `Counter` over
those same rounded endpoints for the degrees.
