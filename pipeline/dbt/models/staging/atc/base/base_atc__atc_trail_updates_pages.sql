-- ATC's Trail Updates as their website shows them (extract/atc/closures.py's
-- third resource, extract/_kinds.py's AtcTrailUpdatePages): one row per
-- update ATC's trail-updates sitemap lists, as lib/atc_scrape.py's
-- parse_update() reads its page, keyed (decision 40), with nothing filtered
-- and nothing joined. Which rows may publish without a person is
-- int_closures__atc_automatic's (CL07-CL10).
--
-- `states` and `miles` stay JSON, as the extract landed them: a mile is the
-- number the parse read, which int_closures__atc_automatic carries as its
-- JSON text so a writer prints the digits Python's json.dumps() prints.
--
-- Key: the registry key and ATC's slug. The resource keeps each slug's first
-- mention in the sitemap, so the slug is unique by construction, and the
-- raw table's own unique test holds it.
with source as (
    select * from {{ source('atc', 'raw_atc__atc_trail_updates_pages') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'atc_trail_updates'",
            'slug',
        ]) }} as atc_trail_update_page_key,
        slug,
        _row as sitemap_row,
        sitemap_lastmod,
        title,
        category,
        cast(states as json) as states,
        date_modified,
        date_published,
        cast(miles as json) as miles,
        source_url,
        page_sha256,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='atc_trail_update_page_key', order_by='_dlt_id'
) }}
