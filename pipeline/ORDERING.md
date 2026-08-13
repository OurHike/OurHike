# Ordering the centerline pieces

What `export_elevation.py` does to put ATC's centerline in trail order, why it
is wrong in a measurable way, what the source geometry actually looks like, and
which fixes have been tried and rejected.

**This is a record, not a plan.** The ordering is a known-open problem
(**#652 — The elevation profile's mile axis is out of order in 18 places, by up
to 46 miles**) and is deliberately not being worked. It is written down because
the measurements below cost a couple of hours and would otherwise have to be
re-derived from issue comments by whoever picks it up.

**It is also not a blocker for the gain figures any more.** #559 is fixed by
marking the seams rather than by ordering them correctly — see
`export_elevation.py`'s docstring point 4 — and that fix stays correct however
good the ordering ever gets. What ordering still affects is `distance_mi`: a
sample's mile is its position in the sorted sequence, so where the sort is
wrong, the mile axis is wrong.

## What it does today

`ordered_oriented_parts()` reverses any piece whose own coordinates run
north-to-south, then sorts every piece by its start point's
`_trail_axis_projection` — the projection onto a straight Springer→Katahdin
line. The function's docstring is upfront that this is a geographic
approximation rather than a reconstruction, since `centerline.geojson` carries
no trail-sequence field.

## What that costs, measured

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

## What a real attempt would probably need

In this order, none of it verified:

1. **Dedupe the overlapping geometry first.** The degree-6 nodes are the
   blocker, and they are upstream of any walking strategy. Worth finding out
   whether they are exact duplicate segments, near-duplicates from separate
   surveys, or genuine multi-way junctions that mean something.
2. **Walk each component** once its nodes are mostly degree ≤ 2, starting from
   a degree-1 end. Five components, so five walks.
3. **Order the five chains geographically** — this is the only step the current
   straight-axis projection is actually suited to, and with five items instead
   of 558 its failure modes stop mattering.
4. **Check it with the numbers above**, which is what makes this tractable to
   verify: total gap should collapse toward the five real discontinuities, and
   `check_elevation_gain.py`'s step-plausibility report should stop finding
   impossible steps anywhere except those five.

## Reproducing any of this

Fetch the centerline (`lib/arcgis.fetch_layer_to_file` off `sources.json`),
then in DuckDB with `spatial`, reusing the module's own functions:

```python
parts = reproject_lines_to_meters(con, ordered_oriented_parts(load_merged_trail_line(con, CENTERLINE_PATH)))
```

Everything above is arithmetic on `parts` — endpoint distances for the gaps,
union-find over endpoints rounded to 1 m for the components, a `Counter` over
those same rounded endpoints for the degrees.
