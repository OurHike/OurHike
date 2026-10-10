-- NYNJTC's Trail Alerts posts, read as lib/nynjtc_alerts.py's parse_alert()
-- reads them and shaped as its published_rows() publishes them (WN05-WN08),
-- one row per post, with why it cannot be read in `problems`. An empty list
-- means the post publishes. int_closures__gate holds NYNJTC's whole file
-- back on any problem, as fetch_nynjtc_alerts.py leaves the previous cache in
-- place rather than cache the subset that still parsed ("Zero tolerance"),
-- and on a category with no posts at all, which it reads as a broken parse.
--
-- A POST IS READABLE (parse_alert's "required four") with a slug that is
-- not blank, a `modified`, a link starting "http", and a title that is not
-- empty once read. The title is read as _text_of() reads it: tags become
-- spaces, entities are unescaped, whitespace runs become one space, the
-- ends are stripped, and entities are unescaped once more (WordPress sends
-- `&amp;#8211;` for a typed `&#8211;`). python_strip()'s class is
-- str.isspace()'s, which is what Python's `\s` matches in a str pattern.
--
-- PLACE TERMS (WN05) resolve against the daily vocabulary: an id the post
-- carries that the vocabulary holds, in the post's own order; an id it does
-- not hold is dropped, never faked (parse_alert's terms_for()). A term needs
-- an id, a name and a slug, and its name is unescaped once (parse_terms()).
-- `locality` (WN07) is the regions, else the states, else the parks: each
-- name that is not blank, once, in order (published_rows()'s locality_of()).
--
-- `updated_at` (WN08) is `modified`, NYNJTC's site-local time written as UTC
-- to the second: a known error of a few hours, carried, as _as_utc_stamp()
-- carries it. Nothing here places, classifies or reviews a post (WN06):
-- that is int_closures__unioned's null `obstructs_trail`, by decision 7.
--
-- STRICTER THAN THE PYTHON, deliberately, each a post the Python would read:
-- two posts with one slug are a problem here, where the cache keeps whichever
-- came last, and a `title.rendered` that is not a string reads as no title,
-- where _text_of() prints whatever it is. WordPress keeps a slug unique within
-- posts and renders every title as a string, so neither has happened. And a
-- link back into the app (macros/link_into_the_app.sql, decision 94) is a
-- problem here, which the Python reads as any other "http" link.
with posts as (
    select * from {{ ref('base_nynjtc__nynjtc_trail_alerts') }}
),

terms as (
    select * from {{ ref('base_nynjtc__nynjtc_trail_alerts_terms') }}
),

-- parse_terms(): a term with an id, a name and a slug; its name unescaped.
vocabulary as (
    select
        taxonomy,
        term_id,
        {{ python_html_unescape('term_name') }} as term_name
    from terms
    where term_id is not null and term_name is not null and slug is not null
),

tag_lists as (
    select
        trail_alert_key,
        'trail' as taxonomy,
        trail_term_ids as term_ids
    from posts
    union all
    select
        trail_alert_key,
        'park' as taxonomy,
        park_term_ids as term_ids
    from posts
    union all
    select
        trail_alert_key,
        'region' as taxonomy,
        region_term_ids as term_ids
    from posts
    union all
    select
        trail_alert_key,
        'state' as taxonomy,
        state_term_ids as term_ids
    from posts
),

tag_items as (
    select
        trail_alert_key,
        taxonomy,
        cast(term_ids as json[]) as term_ids
    from tag_lists
    where json_type(term_ids) = 'ARRAY'
),

tags as (
    select
        trail_alert_key,
        taxonomy,
        unnest(term_ids) as term_id_json,
        generate_subscripts(term_ids, 1) as tag_position
    from tag_items
),

named_tags as (
    select
        tags.trail_alert_key,
        tags.taxonomy,
        tags.tag_position,
        vocabulary.term_name
    from tags
    inner join vocabulary
        on
            tags.taxonomy = vocabulary.taxonomy
            and json_type(tags.term_id_json) in ('UBIGINT', 'BIGINT')
            and cast(json_extract_string(tags.term_id_json, '$') as bigint)
            = vocabulary.term_id
),

-- locality_of(): a taxonomy's names that are not blank, each once, in the
-- order the post first names them.
-- features/ORG_NOTICES.md section 4's left-hand side, for
-- conditions/notices.json's `org_terms` place (decision 53, phase D): each
-- post's trail and park tags as `taxonomy:slug`, keyed on the taxonomy and
-- the slug and never the term id or the bare slug (section 4's three
-- properties), trail tags first and each in the post's own order. No term is
-- mapped to a feature here: no reviewed table exists, so an `org_terms` place
-- places nothing yet, and a phone reads it as unplaced (section 4: "An
-- unmapped term places nothing").
place_slugs as (
    select
        taxonomy,
        term_id,
        {{ python_strip('slug') }} as slug
    from terms
    where
        taxonomy in ('trail', 'park')
        and term_id is not null
        and coalesce({{ python_strip('slug') }}, '') != ''
),

place_tags as (
    select
        tags.trail_alert_key,
        tags.taxonomy,
        place_slugs.slug,
        min(tags.tag_position) as first_position
    from tags
    inner join place_slugs
        on
            tags.taxonomy = place_slugs.taxonomy
            and json_type(tags.term_id_json) in ('UBIGINT', 'BIGINT')
            and cast(json_extract_string(tags.term_id_json, '$') as bigint)
            = place_slugs.term_id
    group by tags.trail_alert_key, tags.taxonomy, place_slugs.slug
),

place_terms as (
    select
        trail_alert_key,
        cast(to_json(list(
            taxonomy || ':' || slug
            order by
                case taxonomy when 'trail' then 0 else 1 end,
                first_position,
                slug
        )) as varchar) as place_terms
    from place_tags
    group by trail_alert_key
),

locality_names as (
    select
        trail_alert_key,
        taxonomy,
        term_name,
        min(tag_position) as first_position
    from named_tags
    where {{ python_strip('term_name') }} != ''
    group by trail_alert_key, taxonomy, term_name
),

localities as (
    select
        trail_alert_key,
        taxonomy,
        string_agg(term_name, ', ' order by first_position) as term_names
    from locality_names
    group by trail_alert_key, taxonomy
),

read_posts as (
    select
        posts.trail_alert_key,
        posts.post_id,
        posts.modified_at,
        posts.link,
        posts._loaded_at,
        {{ python_strip('posts.slug') }} as slug,
        -- The rendered HTML, where WordPress sent it as a string. Anything
        -- else reads as no title (stricter: _text_of() would print a number).
        case
            when
                json_type(json_extract(posts.title_json, '$.rendered'))
                = 'VARCHAR'
                then json_extract_string(posts.title_json, '$.rendered')
            else ''
        end as rendered_title,
        coalesce(
            region.term_names, state.term_names, park.term_names, ''
        ) as locality
    from posts
    left join localities as region
        on
            posts.trail_alert_key = region.trail_alert_key
            and region.taxonomy = 'region'
    left join localities as state
        on
            posts.trail_alert_key = state.trail_alert_key
            and state.taxonomy = 'state'
    left join localities as park
        on
            posts.trail_alert_key = park.trail_alert_key
            and park.taxonomy = 'park'
),

-- _text_of(), a step at a time: strip_html() tags out, entities in,
-- whitespace flattened and the ends stripped; then html.unescape() again.
untagged as (
    select
        *,
        {{ python_html_unescape(
            "regexp_replace(rendered_title, '<[^>]+>', ' ', 'g')"
        ) }} as unescaped_once
    from read_posts
),

flattened as (
    select
        *,
        {{ python_strip(
            "regexp_replace(unescaped_once, '[\\s\\x{0b}\\x{1c}-\\x{1f}\\x{85}\\p{Z}]+', ' ', 'g')"
        ) }} as stripped_html
    from untagged
),

titled as (
    select
        *,
        {{ python_html_unescape('stripped_html') }} as title
    from flattened
),

counted as (
    select
        *,
        count(*) over (partition by slug) as posts_with_slug
    from titled
),

-- Why a post cannot be read, each named by the post's slug, or its id where
-- it has none (fetch_nynjtc_alerts.py's "Could not read N: <slug or id>").
checked as (
    select
        *,
        list_transform(
            list_filter(
                [
                    case when coalesce(slug, '') = '' then 'no slug' end,
                    case when modified_at is null then 'no modified date' end,
                    case
                        when not coalesce(starts_with(link, 'http'), false)
                            then 'a link that is not http'
                    end,
                    -- Decision 94: not back into the app, which
                    -- parse_alert() does not check.
                    case
                        when coalesce(starts_with(link, 'http'), false)
                            then
                                'a link that '
                                || ({{ link_into_the_app('link') }})
                    end,
                    case
                        when coalesce(title, '') = '' then 'no title once read'
                    end,
                    case
                        when coalesce(slug, '') != '' and posts_with_slug > 1
                            then 'a slug another post also has'
                    end
                ],
                lambda p: p is not null
            ),
            lambda p: coalesce(nullif(slug, ''), 'post ' || post_id)
            || ': '
            || p
        ) as problems
    from counted
)

select
    checked.trail_alert_key,
    checked.post_id,
    checked.slug,
    -- features/ORG_NOTICES.md's `<source key>:<the org's own slug>`. A post
    -- that cannot be read, or shares its slug, is named by its WordPress id
    -- instead, so the id is unique in the union whatever the source sent.
    case
        when coalesce(checked.slug, '') != '' and checked.posts_with_slug = 1
            then 'nynjtc_trail_alerts:' || checked.slug
        else 'nynjtc_trail_alerts:post-' || checked.post_id
    end as notice_id,
    checked.title,
    checked.locality,
    checked.link as source_url,
    checked.modified_at,
    {{ python_utc_seconds('checked.modified_at') }} as updated_at,
    checked.problems,
    nullif(array_to_string(checked.problems, ' | '), '') as problem,
    place_terms.place_terms,
    checked._loaded_at
from checked
left join place_terms on checked.trail_alert_key = place_terms.trail_alert_key
