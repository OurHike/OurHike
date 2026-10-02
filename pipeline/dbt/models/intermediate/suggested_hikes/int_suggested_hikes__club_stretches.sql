-- INTERFACE: replace with trail_lines' model
--
-- The maintaining clubs' stretches of the A.T., which a highlight's `club` is
-- read from (lib/highlights.py's club_for_mile()): club_sections.json's
-- `clubs`, which export_club_sections.py writes today, one row per stretch,
-- `club_order` the club's place in that list and `stretch_order` the
-- stretch's place in its club's `stretches`, each from 0. `acronym` is null
-- where the file's is not a string, and start_mile or end_mile null where
-- it is not a number, which club_for_mile() skips.
--
-- Zero rows until the trail_lines family writes club_sections.json from SQL
-- (stage 3 of #1793 — Rebuild the data platform as dlt → dbt: seven
-- contracted marts, a monthly refresh, published docs, and lighter phone
-- downloads), so every highlight's club is null, which is
-- export_highlights.py's own answer with no club_sections.json: "Missing club
-- sections cost the report and nothing else". It reads ATC's club sections
-- only so that it is not a root model.
select
    cast(null as varchar) as acronym,
    cast(null as double) as start_mile,
    cast(null as double) as end_mile,
    cast(null as bigint) as club_order,
    cast(null as bigint) as stretch_order
from {{ ref('stg_atc__club_sections') }}
where false
