-- STAND-IN, deleted at merge. The real int_trail_lines__coded_domains is
-- tl-at's (the A.T. half of the trail_lines port, stage 3 of #1793 — Rebuild
-- the data platform as dlt → dbt: seven contracted marts, a monthly refresh,
-- published docs, and lighter phone downloads): each ArcGIS coded domain a
-- line source's blaze field decodes against, which export_trails.py fetches
-- live today (lib/arcgis.py's get_field_coded_domain, TL02). This file holds
-- its columns and no rows, so int_trail_lines__blazes builds on this branch
-- before tl-at's model exists. With no rows, every side_trails blaze reads
-- as undecodable here, which is the Python's own answer when the live
-- domain call returns nothing.
--
-- It reads int_sources__publication only so that it is not a root model,
-- which the project evaluator refuses. Not stg_registry__sources, which
-- int_trail_lines__blazes also reads: the evaluator reads a single-use model
-- between a parent and its child as an upstream concept rejoined.
select
    cast(source_key as varchar) as source_key,
    cast(null as varchar) as field_name,
    cast(null as varchar) as code,
    -- Quoted because `label` is a keyword to SQLFluff's RF04, and the column
    -- is named so in the lead's spec for tl-at's model; quoting it is what
    -- RF06 calls unnecessary, so RF06 is waived on this one line.
    cast(null as varchar) as "label"  -- noqa: RF06
from {{ ref('int_sources__publication') }}
where false
