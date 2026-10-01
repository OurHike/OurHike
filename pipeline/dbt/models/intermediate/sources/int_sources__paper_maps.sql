-- Each landed paper-map table (#1574), its products in publishable shape and
-- the first problem export_sources.py's `_paper_maps` would refuse it for.
-- One row per table file, which a store block names by path. The problem
-- reaches the build through int_sources__stewards, and only for a table a
-- shipping steward's store block names, as `_paper_maps` runs only then.
--
-- THE CHECKS, IN `_paper_maps`'S ORDER, the first failure being the table's:
-- the table holds products and an https `store.base`; then, product by
-- product, its handle is a Shopify handle, its title is not blank, it lists
-- sheets, each sheet is a sheet number listed by no earlier product or entry,
-- `sheet_covers` names exactly its sheets, each with a list of place names,
-- and `covers`, where present, is a list of place names. The two patterns
-- are vars held to the Python's by tests/test_dbt_sources_parity.py.
--
-- Stricter than `_paper_maps` in one place, as int_podcasts__checked is: a
-- handle or sheet number must end at its last character, where re.match's
-- `$` also matches before a trailing newline. Messages render values as
-- JSON, where the Python uses repr, and name the path as it was landed.
with tables as (
    select * from {{ ref('base_registry__nynjtc_paper_maps') }}
),

files as (
    select
        file_path,
        json_extract(document_json, '$.maps') as maps_json,
        json_extract(document_json, '$.store.base') as base_json
    from tables
),

file_checks as (
    select
        file_path,
        maps_json,
        json_extract_string(base_json, '$') as store_base,
        case
            when
                not coalesce(
                    json_type(maps_json) = 'ARRAY'
                    and json_array_length(maps_json) > 0,
                    false
                )
                then
                    file_path || ' carries no `maps` - the paper-map table '
                    || 'needs at least one product'
            when
                not coalesce(
                    json_type(base_json) = 'VARCHAR'
                    and starts_with(
                        json_extract_string(base_json, '$'), 'https://'
                    ),
                    false
                )
                then
                    file_path || ' needs `store.base` - the https origin '
                    || 'every product handle is a path under'
        end as file_problem
    from files
),

products as (
    select
        file_path,
        store_base,
        unnest(cast(maps_json as json[])) as product,
        generate_subscripts(cast(maps_json as json[]), 1) as product_number
    from file_checks
    where json_type(maps_json) = 'ARRAY'
),

fields as (
    select
        file_path,
        store_base,
        product_number,
        product,
        json_extract(product, '$.handle') as handle_json,
        json_extract_string(product, '$.handle') as handle,
        json_extract(product, '$.title') as title_json,
        json_extract(product, '$.sheets') as sheets_json,
        json_extract(product, '$.sheet_covers') as sheet_covers_json,
        json_extract(product, '$.covers') as covers_json,
        -- `covers` is optional; present, it is a list of place names.
        json_extract(product, '$.covers') is null
        or coalesce(
            json_type(json_extract(product, '$.covers')) = 'ARRAY'
            and list_bool_and(list_transform(
                cast(json_extract(product, '$.covers') as json[]),
                lambda name: json_type(name) = 'VARCHAR'
                and {{ python_strip("json_extract_string(name, '$')") }} != ''
            )) is not false,
            false
        ) as covers_are_names
    from products
),

-- Each sheet a product lists, in product and then list order, the order
-- `_paper_maps` meets them in. A repeat is any later listing of a sheet an
-- earlier entry, in this product or another, already listed.
sheets as (
    select
        file_path,
        product_number,
        handle,
        unnest(cast(sheets_json as json[])) as sheet_json,
        generate_subscripts(cast(sheets_json as json[]), 1) as sheet_number
    from fields
    where json_type(sheets_json) = 'ARRAY'
),

sheet_listings as (
    select
        *,
        case
            when
                json_type(sheet_json) = 'VARCHAR'
                and regexp_full_match(
                    json_extract_string(sheet_json, '$'),
                    '{{ var("registry_sheet_number_pattern") }}'
                )
                then json_extract_string(sheet_json, '$')
        end as sheet
    from sheets
),

sheet_checks as (
    select
        file_path,
        product_number,
        sheet_number,
        json_extract_string(sheet_json, '$') as sheet_text,
        case
            when sheet is null
                then
                    file_path || ': product ' || handle || ' lists sheet '
                    || cast(sheet_json as varchar)
                    || ', which is not a sheet number like 118 or 106A'
            when
                row_number() over (
                    partition by file_path, sheet
                    order by product_number, sheet_number
                ) > 1
                then
                    file_path || ': sheet ' || sheet || ' is listed by both '
                    || first_value(handle)
                        over (
                            partition by file_path, sheet
                            order by product_number, sheet_number
                        )
                    || ' and ' || handle || '; a sheet belongs to one product'
        end as sheet_problem
    from sheet_listings
),

sheet_problems as (
    select
        file_path,
        product_number,
        arg_min(sheet_problem, sheet_number)
        filter (where sheet_problem is not null) as sheet_problem,
        list(sheet_text order by sheet_number) as sheet_list
    from sheet_checks
    group by file_path, product_number
),

-- Each `sheet_covers` entry, in the object's own order, which is the order
-- `_paper_maps` checks them in.
covered as (
    select
        file_path,
        product_number,
        handle,
        unnest(map_entries(
            cast(sheet_covers_json as map (varchar, json))
        )) as entry,
        generate_subscripts(map_keys(
            cast(sheet_covers_json as map (varchar, json))
        ), 1) as entry_number
    from fields
    where json_type(sheet_covers_json) = 'OBJECT'
),

covered_checks as (
    select
        file_path,
        product_number,
        entry_number,
        case
            when
                not coalesce(
                    json_type(struct_extract(entry, 'value')) = 'ARRAY'
                    and list_bool_and(list_transform(
                        cast(struct_extract(entry, 'value') as json[]),
                        lambda name: json_type(name) = 'VARCHAR'
                        and {{ python_strip(
                            "json_extract_string(name, '$')"
                        ) }} != ''
                    )) is not false,
                    false
                )
                then
                    file_path || ': product ' || handle || ', sheet '
                    || struct_extract(entry, 'key')
                    || ': `sheet_covers` must be a list of place names'
        end as covered_problem
    from covered
),

covered_problems as (
    select
        file_path,
        product_number,
        arg_min(covered_problem, entry_number)
        filter (where covered_problem is not null) as covered_problem
    from covered_checks
    group by file_path, product_number
),

product_checks as (
    select
        fields.file_path,
        fields.product_number,
        coalesce(
            case
                when
                    not coalesce(
                        json_type(fields.handle_json) = 'VARCHAR'
                        and regexp_full_match(
                            fields.handle,
                            '{{ var("registry_product_handle_pattern") }}'
                        ),
                        false
                    )
                    then
                        fields.file_path || ': product handle '
                        || coalesce(cast(fields.handle_json as varchar), 'null')
                        || ' is not a Shopify handle (lowercase words joined '
                        || 'by ''-'')'
            end,
            case
                when
                    not coalesce(
                        json_type(fields.title_json) = 'VARCHAR'
                        and {{ python_strip(
                            "json_extract_string(fields.title_json, '$')"
                        ) }} != '',
                        false
                    )
                    then
                        fields.file_path || ': product ' || fields.handle
                        || ' has no title - the phone prints the title '
                        || 'verbatim, '
                        || 'so it cannot be blank'
            end,
            case
                when
                    not coalesce(
                        json_type(fields.sheets_json) = 'ARRAY'
                        and json_array_length(fields.sheets_json) > 0,
                        false
                    )
                    then
                        fields.file_path || ': product ' || fields.handle
                        || ' lists no sheets'
            end,
            sheet_problems.sheet_problem,
            case
                when
                    not coalesce(
                        json_type(fields.sheet_covers_json) = 'OBJECT'
                        and list_sort(list_distinct(
                            json_keys(fields.sheet_covers_json)
                        ))
                        = list_sort(list_distinct(sheet_problems.sheet_list)),
                        false
                    )
                    then
                        fields.file_path || ': product ' || fields.handle
                        || ' needs a `sheet_covers` entry for every sheet it '
                        || 'lists and no other'
            end,
            covered_problems.covered_problem,
            case
                when not fields.covers_are_names
                    then
                        fields.file_path || ': product ' || fields.handle
                        || ': `covers` must be a list of place names'
            end
        ) as product_problem,
        json_object(
            'handle', fields.handle,
            'title', {{ python_strip(
                "json_extract_string(fields.title_json, '$')"
            ) }},
            'url', fields.store_base || '/products/' || fields.handle,
            'sheets', fields.sheets_json,
            'covers', coalesce(fields.covers_json, cast('[]' as json)),
            'sheet_covers', fields.sheet_covers_json
        ) as product_record
    from fields
    left join sheet_problems
        on
            fields.file_path = sheet_problems.file_path
            and fields.product_number = sheet_problems.product_number
    left join covered_problems
        on
            fields.file_path = covered_problems.file_path
            and fields.product_number = covered_problems.product_number
),

per_file as (
    select
        file_path,
        arg_min(product_problem, product_number)
        filter (where product_problem is not null) as product_problem,
        list(product_record order by product_number) as products
    from product_checks
    group by file_path
)

select
    file_checks.file_path,
    coalesce(per_file.products, []) as products,
    coalesce(
        file_checks.file_problem, per_file.product_problem
    ) as problem
from file_checks
left join per_file on file_checks.file_path = per_file.file_path
