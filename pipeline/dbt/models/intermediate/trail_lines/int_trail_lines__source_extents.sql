{{ config(materialized='table') }}
-- One row per trail-line layer int_trail_lines__unioned holds: its row
-- count, how many rows carry a geometry, the extent of those rows' own
-- vertices, and the narrowest of macros/lands_outside_its_region.sql's boxes
-- the vertices fit (vertex_region).
--
-- A REGION BOX IS SET FROM VERTICES, NEVER FROM A SERVER'S EXTENT
-- (pipeline/ELT.md, "What wave 1's live reads found that phase C must
-- honour"); int_places__source_extents says why. The trail-line rows' own
-- boxes in lands_outside_its_region.sql were set from each layer's
-- returnExtentOnly but one (2026-10-03), so this model, built on a live
-- run, is what checks them.
{{ vertex_extents(ref('int_trail_lines__unioned')) }}
