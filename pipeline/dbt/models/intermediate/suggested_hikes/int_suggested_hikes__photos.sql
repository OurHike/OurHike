-- The photographs a person confirmed, one row per hike number: the join
-- export_suggested_hikes.py's confirmed_photos() and photo_for() read from
-- reference/nynjtc_hike_photos.json (SH09). Not the matcher's proposal, which
-- is a score about strings: this file is a reviewer's answer about the world,
-- row by row, and no other input can put a photograph on a card.
--
-- A ROW NEEDS ALL THREE OF hike, digest and credit, each read for its own
-- truth as Python reads it (python_truthy): the credit is a CONDITION of the
-- permission these photographs ship on (sources.json's nynjtc_hikes_licence),
-- so a row naming no photographer ships no photograph, whoever confirmed it.
-- A credit of only whitespace is one: confirmed_photos() keeps it, and
-- photo_for() then prints "Photo by " with nobody after it. This model refuses
-- it, the one place it is stricter than the Python (tests/
-- test_dbt_suggested_hikes_parity.py lists it), because a photograph with an
-- empty credit is the attribution the licence requires, missing.
--
-- BOTH SPELLINGS OF THE HIKE ID JOIN: the part after the last colon is the
-- key, so the sheet's bare `50` and the record's `nynjtc_hike_finder:50`
-- meet. The first confirmed row for a number wins (setdefault), in the file's
-- order. A hike id or credit that is not a string or a number confirms
-- nothing; confirmed_photos() would print its Python repr, which no hike
-- number equals.
--
-- `photo_url` is the bucket key, `photos/<digest>.jpg`, the content-addressed
-- store the POI cards draw from (lib/photo_store.py's photo_key()), never an
-- absolute address. photo_key() raises on a digest that is not 64 lowercase
-- hex characters, which fails the whole export; here the same row fails the
-- build, through the mart's test, for a hike the shelf carries.
with photos as (
    select * from {{ ref('base_nynjtc__nynjtc_hike_photos') }}
),

read_rows as (
    select
        file_row,
        json_type(photo) = 'OBJECT' as is_object,
        json_extract(photo, '$.hike_id') as hike_id_json,
        json_extract(photo, '$.digest') as digest_json,
        json_extract(photo, '$.credit') as credit_json
    from photos
),

scalars as (
    select
        file_row,
        is_object,
        {{ python_truthy('hike_id_json') }}
        and {{ python_truthy('digest_json') }}
        and {{ python_truthy('credit_json') }} as names_all_three,
        case
            when
                json_type(hike_id_json) in ('VARCHAR', 'BIGINT', 'UBIGINT')
                then json_extract_string(hike_id_json, '$')
        end as hike_id_text,
        case
            when json_type(digest_json) = 'VARCHAR'
                then json_extract_string(digest_json, '$')
        end as digest,
        case
            when json_type(credit_json) = 'VARCHAR'
                then {{ python_strip("json_extract_string(credit_json, '$')") }}
            when json_type(credit_json) in ('BIGINT', 'UBIGINT', 'DOUBLE')
                then json_extract_string(credit_json, '$')
        end as credit_text,
        json_type(digest_json) as digest_json_type
    from read_rows
),

confirmed as (
    select
        -- str(hike_id).split(":")[-1]: everything after the last colon.
        list_extract(string_split(hike_id_text, ':'), -1) as hike_key,
        file_row,
        digest,
        digest_json_type,
        credit_text
    from scalars
    where
        is_object
        and names_all_three
        and hike_id_text is not null
        and coalesce(credit_text, '') != ''
)

select
    hike_key,
    file_row,
    digest,
    -- A digest that is not a sha256 hex string: photo_key() raises on it.
    coalesce(
        digest_json_type = 'VARCHAR'
        and regexp_full_match(digest, '[0-9a-f]{64}'), false
    ) as digest_is_valid,
    '{{ var("suggested_hikes_photo_prefix") }}/'
    || digest
    || '.{{ var("suggested_hikes_photo_extension") }}' as photo_url,
    -- "Photo by " is the form the licence quotes; a credit that already
    -- carries it, or a "Photo:", is not given it twice.
    case
        when
            starts_with(lower(credit_text), 'photo by')
            or starts_with(lower(credit_text), 'photo:')
            then credit_text
        else 'Photo by ' || credit_text
    end as photo_credit,
    '{{ var("suggested_hikes_photo_licence") }}' as photo_licence
from confirmed
qualify row_number() over (partition by hike_key order by file_row) = 1
