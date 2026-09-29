"""One way to run a vectorised shapely call on every core (#1659, #1660).

Shapely 2 releases the GIL inside its vectorised GEOS calls, so a plain
thread pool runs them in parallel with no process start-up and no pickling
of geometries. Measured 2026-09-24 on a 4-core sandbox against the real
network and centerline:

- `build_trail_graph._split_all`: `line_locate_point` 26.6 s -> 7.9 s and
  `line_interpolate_point` 10.1 s -> 5.0 s;
- `export_trails.vertex_miles`: `STRtree.nearest` on 54,192 centerline
  vertices 22.4 s -> 5.7 s.

The answers are identical to one call over the whole array, and the tests
of both callers check that to the bit: each element is the same GEOS
function on the same inputs, and the chunks are rejoined in their original
order. That holds only for element-wise calls. A function whose answer for
one element depends on the others in the array - a union, a clustering -
does not belong here.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import numpy as np

# A ceiling, not a target: every workflow runs on `ubuntu-latest`, which
# GitHub documents as four cores for a public repository, so CI never reaches
# it. @unvalidated: nobody has timed more than four threads, and a laptop
# with sixteen cores may do better with a higher one.
MAX_WORKERS = 8


def across_cores(function: Callable[..., np.ndarray], *arrays: np.ndarray, chunks: int = 64) -> np.ndarray:
    """`function(*arrays)` computed on matching slices of `arrays`, a thread
    per core, rejoined in order. Every array must be the same length; a
    zero-length input is passed straight through so `function` still decides
    the empty result's dtype."""
    size = len(arrays[0])
    if size == 0:
        return function(*arrays)
    workers = min(MAX_WORKERS, os.cpu_count() or 1)
    slices = np.array_split(np.arange(size), min(chunks, size))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda part: function(*(array[part] for array in arrays)), slices))
    return np.concatenate(results)
