-- NYNJTC's Trail Alerts posts (extract/nynjtc/closures.py), keyed (decision
-- 40), with nothing filtered and nothing joined. Reading a post is the
-- work of int_closures__nynjtc_checked, which does what lib/nynjtc_alerts.py's
-- parse_alert() does: unescape the title, resolve the place-term ids.
--
-- The body (`content`) and excerpt are left behind here: they are NYNJTC's
-- writing, nynjtc_notices_licence authorises none of it, and nothing
-- downstream reads them. `modified` is the alert's own date
-- (lib/nynjtc_alerts.py's ParsedAlert: NYNJTC edits alerts in place).
-- WordPress writes it site-local with no offset, and dlt read it as UTC,
-- which is what lib/nynjtc_alerts.py's _as_utc_stamp() does with it too:
-- the same known error of a few hours, carried rather than hidden (WN08).
--
-- Key: the post's WordPress id.
with source as (
    select * from {{ source('nynjtc', 'raw_nynjtc__nynjtc_trail_alerts') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'nynjtc_trail_alerts'",
            'id',
        ]) }} as trail_alert_key,
        id as post_id,
        slug,
        link,
        cast(title as json) as title_json,
        modified as modified_at,
        cast(trail as json) as trail_term_ids,
        cast(park as json) as park_term_ids,
        cast(region as json) as region_term_ids,
        cast(state as json) as state_term_ids,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='trail_alert_key', order_by='_dlt_id'
) }}
