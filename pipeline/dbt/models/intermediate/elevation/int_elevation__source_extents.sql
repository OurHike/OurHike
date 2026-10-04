{{ config(materialized='table') }}
-- One row per elevation layer int_elevation__unioned holds: its row count,
-- how many rows carry a geometry, the extent of those rows' own vertices,
-- and the narrowest of macros/lands_outside_its_region.sql's boxes the
-- vertices fit (vertex_region).
--
-- A REGION BOX IS SET FROM VERTICES, NEVER FROM A SERVER'S EXTENT
-- (pipeline/ELT.md, "What wave 1's live reads found that phase C must
-- honour"); int_places__source_extents says why. A row with no geometry
-- (ATC's ATX centerline repeats segment 25-01-03 18 times with none) counts
-- in row_count and not in rows_with_geometry.
{{ vertex_extents(ref('int_elevation__unioned')) }}
