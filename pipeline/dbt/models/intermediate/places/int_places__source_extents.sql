{{ config(materialized='table') }}
-- One row per places layer int_places__unioned holds: its row count, how
-- many rows carry a geometry, the extent of those rows' own vertices, and
-- the narrowest of macros/lands_outside_its_region.sql's boxes the vertices
-- fit (vertex_region).
--
-- A REGION BOX IS SET FROM VERTICES, NEVER FROM A SERVER'S EXTENT
-- (pipeline/ELT.md, "What wave 1's live reads found that phase C must
-- honour"): USFWS's trail segments answered returnExtentOnly with lat
-- -24.99 to 90 while their vertices span lat 13.64 to 63.20 (2026-10-03).
-- macros/generated_regions.sql gives every generated source the widest box
-- that still catches a swap, and this model, built on the rows a live run
-- landed, is what a narrower box for a source is read from.
--
-- THE STRAY POINTS the union cleared (its `point_outside_region`) are
-- counted per layer, `points_outside_region`, and
-- `loses_too_many_points_outside_region` says whether that is too many to
-- be data-entry errors (macros/lands_outside_its_region.sql's
-- loses_too_many_points_outside_its_region): the test that fails a point
-- layer read lon/lat swapped, whose every point the union cleared.
{{ vertex_extents(
    ref('int_places__unioned'), cleared_column='point_outside_region'
) }}
