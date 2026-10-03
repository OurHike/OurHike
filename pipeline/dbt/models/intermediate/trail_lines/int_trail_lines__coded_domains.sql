-- The ArcGIS coded-value domains the trail_lines family decodes against:
-- one row per (source, field, code). export_trails.py and export_spurs.py
-- fetch these live, mid-transform, with lib/arcgis.get_field_coded_domain;
-- here the decode is a join (pipeline/ELT.md's TL02), against a frozen copy.
--
-- @unvalidated AS A COPY: the trail_lines_coded_domains var in
-- dbt_project.yml was read from side_trails' live field metadata
-- (`fields[].domain.codedValues`, ANST_Facilities/FeatureServer/6) on
-- 2026-10-02, and nothing re-reads it, so a code ATC adds would decode as
-- unknown here while the Python decoded it. What settles it is the extract
-- landing each layer's field metadata, which replaces the var in this one
-- model; the columns stay (source_key, field_name, code, label).
--
-- `field_name` is spelled as the layer and sources.json spell it ('Blaze',
-- 'Type'), not as dlt's lowercased column. `code` is text, as side_trails'
-- esriFieldTypeString fields and their values are; export_trails.py's `in`
-- compares types, and on these two fields both sides are text, so a text
-- join answers the same (an integer-coded field landed as text would not).
select
    domains.source_key,
    domains.field_name,
    domains.code,
    domains.label
from (
    values
    {%- for row in var('trail_lines_coded_domains') %}
    (
        '{{ row[0] }}',
        '{{ row[1] }}',
        '{{ row[2] }}',
        '{{ row[3] | replace("'", "''") }}'
    ){{ "," if not loop.last }}
    {%- endfor %}
) as domains (source_key, field_name, code, label)
