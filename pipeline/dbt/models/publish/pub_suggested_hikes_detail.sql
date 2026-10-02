{{ config(
    format='json',
    location='suggested_hikes_detail.json',
    meta={'when_empty': 'keep_last_file'}
) }}
-- Every shipped hike's detail, the fields the shelf leaves out, in shelf
-- order: each the mart's `detail_record`, export_suggested_hikes.py's
-- split_record() half, built and unit-tested in int_suggested_hikes__records.
--
-- ONE FILE FOR ALL OF THEM, `{"details": [...]}`, because a phone_file
-- writes exactly one document and dbt has no per-object fan-out
-- (pipeline/ELT.md, "Four kinds of phone file"). Each detail ships as its own
-- object, `suggested_hikes_detail_<number>.json`, the flat root key
-- write_details() names it under (DETAIL_KEY): cutting this file into those
-- objects is stage 4's, outside dbt, as the per-cell files are, and the key
-- is the number after the id's last colon, which the mart's test holds to
-- detailKeyFor's `<source>:<digits>`. Nothing is written when no hike ships,
-- as for the shelf (pub_suggested_hikes).
with hikes as (
    select * from {{ ref('suggested_hikes') }}
    where phone_file = 'suggested_hikes'
)

select list(detail_record order by list_position) as details
from hikes
having count(*) > 0
