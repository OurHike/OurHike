"""End-to-end test for fetch_and_mosaic_cell.py - the per-cell CI unit of
work, composed entirely from already-unit-tested building blocks
(fetch_quads_for_cell, resolve_state_index, index_quads_in_dir,
mosaic_one_cell, fix_quad). This test exists to catch wiring mistakes
between those pieces (wrong path threaded through, wrong argument order)
that per-function unit tests can't see, not to re-test their internals.

All HTTP mocked (requests_mock) - no real network, matching this project's
established testing convention (see TESTING.md).
"""

import json

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds

import fix_corrupted_quads
from fetch_and_mosaic_cell import run_cell
from fetch_topo_quads import BUCKET_URL, GEOTIFF_PREFIX

S3_LISTING_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Contents><Key>{GEOTIFF_PREFIX}/CT/CT_Ansonia_20240815_TM_geo.tif</Key></Contents>
  <IsTruncated>false</IsTruncated>
</ListBucketResult>"""

TIF_URL = f"{BUCKET_URL}/{GEOTIFF_PREFIX}/CT/CT_Ansonia_20240815_TM_geo.tif"


def _write_corridor(path, west, south, east, north):
    geometry = {"type": "Polygon", "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]]}
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": geometry}]})
    )


def _write_quad_geotiff(path, bounds, size=60, fill=200):
    transform = from_bounds(*bounds, size, size)
    profile = {
        "driver": "GTiff",
        "height": size,
        "width": size,
        "count": 1,
        "dtype": "uint8",
        "crs": "EPSG:4326",
        "transform": transform,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(np.full((1, size, size), fill, dtype="uint8"))
    return path.read_bytes()


def test_run_cell_fetches_mosaics_and_writes_a_tile(tmp_path, requests_mock):
    # The cell and the corridor are the same small square - so the final
    # corridor-clip step doesn't zero anything out, isolating "does the
    # per-cell fetch+mosaic pipeline wire together correctly" from clip-
    # boundary behavior, which is already covered in test_spike_raster_mosaic.py.
    cell_bbox = (-74.06, 41.00, -74.00, 41.06)
    corridor_path = tmp_path / "corridor.geojson"
    _write_corridor(corridor_path, *cell_bbox)

    cells_json = tmp_path / "cells.json"
    cells_json.write_text(json.dumps({"cells": [{"index": 0, "bbox": list(cell_bbox), "quads": ["CT_Ansonia.pdf"]}]}))

    metadata_csv = tmp_path / "ustopo_current.csv"
    metadata_csv.write_text(
        f"product_filename,westbc,eastbc,northbc,southbc\nCT_Ansonia.pdf,{cell_bbox[0]},{cell_bbox[2]},{cell_bbox[3]},{cell_bbox[1]}\n"
    )

    requests_mock.get(BUCKET_URL, content=S3_LISTING_XML.encode())
    requests_mock.head(TIF_URL, headers={"Last-Modified": "Tue, 01 Jul 2025 00:00:00 GMT"})
    requests_mock.get(TIF_URL, content=_write_quad_geotiff(tmp_path / "source_quad.tif", cell_bbox))

    out_dir = tmp_path / "out"
    scratch_dir = tmp_path / "scratch"

    out_path = run_cell(0, cells_json, metadata_csv, corridor_path, out_dir, scratch_dir)

    assert out_path == out_dir / "tile_000.tif"
    with rasterio.open(out_path) as src:
        assert src.read(1).max() == 200
        assert src.crs == "EPSG:4326"


def test_run_cell_recovers_a_corrupted_quad_via_reactive_fix(tmp_path, requests_mock):
    """The one genuinely new piece of wiring fetch_and_mosaic_cell.py adds
    over the whole-corridor scripts: a quad that fails validation gets
    fixed inline (redownload-then-fallback) and still contributes to the
    mosaic, rather than being silently dropped or requiring a separate
    manual fix_corrupted_quads.py pass."""
    cell_bbox = (-74.06, 41.00, -74.00, 41.06)
    corridor_path = tmp_path / "corridor.geojson"
    _write_corridor(corridor_path, *cell_bbox)

    cells_json = tmp_path / "cells.json"
    cells_json.write_text(
        json.dumps({"cells": [{"index": 0, "bbox": list(cell_bbox), "quads": ["CT_Ansonia.pdf", "CT_Broken.pdf"]}]})
    )

    metadata_csv = tmp_path / "ustopo_current.csv"
    metadata_csv.write_text(
        "product_filename,westbc,eastbc,northbc,southbc\n"
        f"CT_Ansonia.pdf,{cell_bbox[0]},{cell_bbox[2]},{cell_bbox[3]},{cell_bbox[1]}\n"
        f"CT_Broken.pdf,{cell_bbox[0]},{cell_bbox[2]},{cell_bbox[3]},{cell_bbox[1]}\n"
    )

    listing_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Contents><Key>{GEOTIFF_PREFIX}/CT/CT_Ansonia_20240815_TM_geo.tif</Key></Contents>
  <Contents><Key>{GEOTIFF_PREFIX}/CT/CT_Broken_20240815_TM_geo.tif</Key></Contents>
  <IsTruncated>false</IsTruncated>
</ListBucketResult>"""
    requests_mock.get(BUCKET_URL, content=listing_xml.encode())

    requests_mock.head(TIF_URL, headers={"Last-Modified": "Tue, 01 Jul 2025 00:00:00 GMT"})
    requests_mock.get(TIF_URL, content=_write_quad_geotiff(tmp_path / "source_quad.tif", cell_bbox))

    broken_url = f"{BUCKET_URL}/{GEOTIFF_PREFIX}/CT/CT_Broken_20240815_TM_geo.tif"
    requests_mock.head(broken_url, headers={"Last-Modified": "Tue, 01 Jul 2025 00:00:00 GMT"})
    # First GET (run_cell's initial fetch loop) returns garbage; the second
    # GET (fix_quad's redownload attempt) returns a valid file - exercises
    # the "corrupted, then fixed by redownload" path specifically.
    requests_mock.get(
        broken_url,
        [
            {"content": b"not a real geotiff"},
            {"content": _write_quad_geotiff(tmp_path / "source_quad_2.tif", cell_bbox)},
        ],
    )

    out_dir = tmp_path / "out"
    scratch_dir = tmp_path / "scratch"

    out_path = run_cell(0, cells_json, metadata_csv, corridor_path, out_dir, scratch_dir)

    with rasterio.open(out_path) as src:
        assert src.read(1).max() == 200  # both quads' fill value - the recovered one contributed too

    # The recovered quad's scratch-dir file is now the valid, fixed version -
    # confirms the fix landed in place rather than only in a fallback copy.
    fixed_path = scratch_dir / "quads" / "CT" / "CT_Broken_20240815_TM_geo.tif"
    with rasterio.open(fixed_path) as src:
        src.read(1)  # should not raise


def test_run_cell_raises_when_the_cell_index_is_not_in_cells_json(tmp_path):
    cells_json = tmp_path / "cells.json"
    cells_json.write_text(json.dumps({"cells": [{"index": 0, "bbox": [-75, 41, -74, 42], "quads": []}]}))

    with pytest.raises(ValueError, match="cell 7"):
        run_cell(7, cells_json, tmp_path / "metadata.csv", tmp_path / "corridor.geojson", tmp_path / "out", tmp_path / "scratch")


def test_run_cell_raises_when_some_but_not_all_assigned_quads_make_it_into_the_mosaic(tmp_path, requests_mock):
    """The partial-quad-loss regression: 2 of the cell's 3 assigned quads
    succeed, the third is corrupted and unfixable (fails both redownload and
    the fallback export service). Before this check existed, run_cell()
    would silently mosaic only the 2 that worked - producing a tile with a
    real coverage hole - and only ever print a warning about the third. It
    must now raise instead."""
    cell_bbox = (-74.06, 41.00, -74.00, 41.06)
    corridor_path = tmp_path / "corridor.geojson"
    _write_corridor(corridor_path, *cell_bbox)

    cells_json = tmp_path / "cells.json"
    cells_json.write_text(
        json.dumps(
            {"cells": [{"index": 0, "bbox": list(cell_bbox), "quads": ["CT_Ansonia.pdf", "CT_Bethel.pdf", "CT_Broken.pdf"]}]}
        )
    )

    metadata_csv = tmp_path / "ustopo_current.csv"
    metadata_csv.write_text(
        "product_filename,westbc,eastbc,northbc,southbc\n"
        f"CT_Ansonia.pdf,{cell_bbox[0]},{cell_bbox[2]},{cell_bbox[3]},{cell_bbox[1]}\n"
        f"CT_Bethel.pdf,{cell_bbox[0]},{cell_bbox[2]},{cell_bbox[3]},{cell_bbox[1]}\n"
        f"CT_Broken.pdf,{cell_bbox[0]},{cell_bbox[2]},{cell_bbox[3]},{cell_bbox[1]}\n"
    )

    listing_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Contents><Key>{GEOTIFF_PREFIX}/CT/CT_Ansonia_20240815_TM_geo.tif</Key></Contents>
  <Contents><Key>{GEOTIFF_PREFIX}/CT/CT_Bethel_20240815_TM_geo.tif</Key></Contents>
  <Contents><Key>{GEOTIFF_PREFIX}/CT/CT_Broken_20240815_TM_geo.tif</Key></Contents>
  <IsTruncated>false</IsTruncated>
</ListBucketResult>"""
    requests_mock.get(BUCKET_URL, content=listing_xml.encode())

    ansonia_url = f"{BUCKET_URL}/{GEOTIFF_PREFIX}/CT/CT_Ansonia_20240815_TM_geo.tif"
    bethel_url = f"{BUCKET_URL}/{GEOTIFF_PREFIX}/CT/CT_Bethel_20240815_TM_geo.tif"
    broken_url = f"{BUCKET_URL}/{GEOTIFF_PREFIX}/CT/CT_Broken_20240815_TM_geo.tif"

    requests_mock.head(ansonia_url, headers={"Last-Modified": "Tue, 01 Jul 2025 00:00:00 GMT"})
    requests_mock.get(ansonia_url, content=_write_quad_geotiff(tmp_path / "ansonia.tif", cell_bbox))

    requests_mock.head(bethel_url, headers={"Last-Modified": "Tue, 01 Jul 2025 00:00:00 GMT"})
    requests_mock.get(bethel_url, content=_write_quad_geotiff(tmp_path / "bethel.tif", cell_bbox))

    requests_mock.head(broken_url, headers={"Last-Modified": "Tue, 01 Jul 2025 00:00:00 GMT"})
    # Every GET for the broken quad returns garbage - both the initial fetch
    # and fix_quad()'s redownload attempt - so redownload can't fix it and
    # fix_quad() falls through to the fallback export service.
    requests_mock.get(broken_url, content=b"not a real geotiff")
    # The fallback export service also fails to return anything rasterio can
    # read, so the fallback recovery fails too - this quad is genuinely
    # unrecoverable, matching test_fix_corrupted_quads.py's own
    # both-paths-fail fixture.
    requests_mock.get(fix_corrupted_quads.EXPORT_URL, content=b"not a real image either")

    out_dir = tmp_path / "out"
    scratch_dir = tmp_path / "scratch"

    with pytest.raises(RuntimeError, match=r"cell 0: 1/3 assigned quads"):
        run_cell(0, cells_json, metadata_csv, corridor_path, out_dir, scratch_dir)

    # The 2 good quads must not have been mosaicked and written anyway.
    assert not (out_dir / "tile_000.tif").exists()


def test_run_cell_raises_when_the_cell_has_no_quads_at_all(tmp_path):
    """A cell with an empty quad list can't produce a tile - this must fail
    loudly (matching the whole-corridor script's completeness invariant),
    not silently skip and leave a coverage gap in the assembled background."""
    cell_bbox = (-74.06, 41.00, -74.00, 41.06)
    corridor_path = tmp_path / "corridor.geojson"
    _write_corridor(corridor_path, *cell_bbox)

    cells_json = tmp_path / "cells.json"
    cells_json.write_text(json.dumps({"cells": [{"index": 0, "bbox": list(cell_bbox), "quads": []}]}))
    # Present but empty of quad rows - realistic (the metadata CSV always
    # exists by the time a per-cell job runs, built once upstream), unlike
    # the "cell 7 doesn't exist" test above where nothing downstream of the
    # cells.json lookup ever runs.
    metadata_csv = tmp_path / "ustopo_current.csv"
    metadata_csv.write_text("product_filename,westbc,eastbc,northbc,southbc\n")

    with pytest.raises(RuntimeError, match="produced no tile"):
        run_cell(0, cells_json, metadata_csv, corridor_path, tmp_path / "out", tmp_path / "scratch")
