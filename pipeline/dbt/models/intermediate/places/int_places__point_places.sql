{{ config(materialized='table') }}
-- The trailheads, parking and towns places.json lists, before anything is
-- measured: export_places.py's load_point_places() and community_states() in
-- SQL (PL05, PL04), in their order.
--
-- PL05, FROM THE PUBLISHED WAYPOINTS. A row is a waypoint a phone already
-- holds (int_places__waypoints, the points_of_interest mart's trailheads,
-- parking and resupply), so a pick here opens a waypoint the app can find,
-- and its published id rides as `poi_id`. In load_point_places()'s order:
-- - a trailhead stays a trailhead, parking stays parking, and resupply is a
--   town ONLY where its source's registry entry says `place_kind: town`
--   (ATC's Communities): a store somebody tagged resupply is not a town;
-- - a row with no source is skipped;
-- - a row with no id, no name or no point is not searchable and does not
--   ship: most of OPRHP's pull-offs and DEC's lots have no name;
-- - a published id two rows carry ships once, the first in waypoint order.
--
-- PL04, A POSTAL CODE ONLY WHERE THE SOURCE OR ITS ORGANIZATION STATES ONE.
-- Every row takes the state its source's organization declares (`state` on
-- the organization in sources.json: NYS OPRHP and NYS DEC publish New York).
-- A town takes the state ATC's Communities layer writes for it, matched by
-- GlobalID, before that. The layer writes the state as a word ("Virginia",
-- once "Virgnia", and blank fourteen times, export_places.py's live read of
-- 2026-09-10), so state_code() reads a two-letter code or a state's name, and
-- anything else is absent: a typo is not a state, and absent means unknown,
-- never guessed. The fifty states and the District are below, as
-- US_STATE_CODES has them; tests/test_dbt_places_parity.py holds the two
-- lists equal.
--
-- The Communities row is read as JSON (`state`, and `globalid` where the
-- staging model carries it, `source_id` where it carries the id under that
-- name), so this reads stg_atc__communities in the shape it has on this
-- branch, which stages no state, and in the shape the points_of_interest
-- port gives it, every column the layer has. Where no state column is
-- staged every town reads its organization's, and ATC's declares none.
with waypoints as (
    select * from {{ ref('int_places__waypoints') }}
),

registry as (
    select * from {{ ref('stg_registry__sources') }}
),

organizations as (
    select * from {{ ref('stg_registry__organizations') }}
),

communities_staged as (
    select * from {{ ref('stg_atc__communities') }}
),

communities as (
    select to_json(communities_staged) as community
    from communities_staged
),

-- US_STATE_CODES: name to postal code.
state_codes (state_name, state_code) as (
    values
    ('alabama', 'AL'), ('alaska', 'AK'), ('arizona', 'AZ'),
    ('arkansas', 'AR'), ('california', 'CA'), ('colorado', 'CO'),
    ('connecticut', 'CT'), ('delaware', 'DE'),
    ('district of columbia', 'DC'), ('florida', 'FL'), ('georgia', 'GA'),
    ('hawaii', 'HI'), ('idaho', 'ID'), ('illinois', 'IL'),
    ('indiana', 'IN'), ('iowa', 'IA'), ('kansas', 'KS'),
    ('kentucky', 'KY'), ('louisiana', 'LA'), ('maine', 'ME'),
    ('maryland', 'MD'), ('massachusetts', 'MA'), ('michigan', 'MI'),
    ('minnesota', 'MN'), ('mississippi', 'MS'), ('missouri', 'MO'),
    ('montana', 'MT'), ('nebraska', 'NE'), ('nevada', 'NV'),
    ('new hampshire', 'NH'), ('new jersey', 'NJ'), ('new mexico', 'NM'),
    ('new york', 'NY'), ('north carolina', 'NC'), ('north dakota', 'ND'),
    ('ohio', 'OH'), ('oklahoma', 'OK'), ('oregon', 'OR'),
    ('pennsylvania', 'PA'), ('rhode island', 'RI'),
    ('south carolina', 'SC'), ('south dakota', 'SD'),
    ('tennessee', 'TN'), ('texas', 'TX'), ('utah', 'UT'),
    ('vermont', 'VT'), ('virginia', 'VA'), ('washington', 'WA'),
    ('west virginia', 'WV'), ('wisconsin', 'WI'), ('wyoming', 'WY')
),

-- state_code(): the code itself, in any case, or a state's name.
community_text as (
    select
        coalesce(
            json_extract_string(community, '$.globalid'),
            json_extract_string(community, '$.source_id')
        ) as global_id_text,
        json_extract_string(community, '$.state') as state_text
    from communities
),

community_words as (
    select
        nullif({{ python_strip('global_id_text') }}, '') as global_id,
        nullif({{ python_strip('state_text') }}, '') as state_word
    from community_text
),

town_states as (
    select
        community_words.global_id,
        coalesce(by_code.state_code, by_name.state_code) as state
    from community_words
    left join state_codes as by_code
        on
            length(community_words.state_word) = 2
            and upper(community_words.state_word) = by_code.state_code
    left join state_codes as by_name
        on lower(community_words.state_word) = by_name.state_name
    where
        community_words.global_id is not null
        and coalesce(by_code.state_code, by_name.state_code) is not null
    -- stg_atc__communities is keyed by GlobalID, so a GlobalID is one row;
    -- this only keeps the choice deterministic should stripping ever make
    -- two ids one.
    qualify
        row_number() over (
            partition by community_words.global_id
            order by coalesce(by_code.state_code, by_name.state_code)
        ) = 1
),

org_states as (
    select
        provider,
        org_state
    from organizations
    where coalesce(org_state, '') != ''
),

kinds (poi_type, kind) as (
    values
    ('trailhead', 'trailhead'),
    ('parking', 'parking'),
    ('resupply', 'town')
),

typed as (
    select
        waypoints.*,
        kinds.kind,
        registry.provider,
        json_extract_string(registry.entry, '$.place_kind') as place_kind
    from waypoints
    inner join kinds on waypoints.poi_type = kinds.poi_type
    left join registry on waypoints.source_key = registry.source_key
    where coalesce(waypoints.source, '') != ''
),

searchable as (
    select
        *,
        nullif({{ python_strip('poi_id') }}, '') as place_id,
        nullif({{ python_strip('name') }}, '') as place_name
    from typed
    where kind != 'town' or coalesce(place_kind, '') = 'town'
),

first_of_each as (
    select * from searchable
    where
        place_id is not null
        and place_name is not null
        and lon is not null
        and lat is not null
    qualify
        row_number() over (partition by place_id order by waypoint_order) = 1
),

joined as (
    select
        first_of_each.*,
        nullif({{ python_strip('first_of_each.source_feature_id') }}, '')
            as community_id
    from first_of_each
)

select
    joined.place_id,
    joined.place_id as poi_id,
    joined.place_name as name,
    joined.kind,
    case
        when joined.kind = 'town'
            then coalesce(town_states.state, org_states.org_state)
        else org_states.org_state
    end as state,
    joined.source,
    joined.lon,
    joined.lat,
    joined.waypoint_order,
    joined.club,
    joined.source_key,
    joined._loaded_at
from joined
left join org_states on joined.provider = org_states.provider
left join town_states on joined.community_id = town_states.global_id
