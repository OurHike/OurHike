-- NYNJTC's four place taxonomies (extract/nynjtc/closures.py's terms
-- resource, read daily), one row per term, keyed (decision 40). The names
-- arrive HTML-escaped as WordPress stores them, and
-- int_closures__nynjtc_checked unescapes them as lib/nynjtc_alerts.py's
-- parse_terms() does.
--
-- Key: the taxonomy and the term's id, because a post's lists name a term by
-- id within its taxonomy.
with source as (
    select *
    from {{ source('nynjtc', 'raw_nynjtc__nynjtc_trail_alerts_terms') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'nynjtc_trail_alerts_terms'",
            'taxonomy',
            'id',
        ]) }} as place_term_key,
        taxonomy,
        id as term_id,
        name as term_name,
        slug,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='place_term_key', order_by='_dlt_id'
) }}
