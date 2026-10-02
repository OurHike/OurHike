{{ config(materialized='table') }}
-- How far ATC says water is from each A.T. shelter and campsite, and the
-- water point export_poi.py synthesizes where that is all anyone knows
-- (PO14, PO15, PO16). One row per POI, plus one per synthesized water point.
--
-- THE DISTANCE AND ITS SOURCE TRAVEL TOGETHER OR NOT AT ALL.
-- reference/water_distance.json (base_atc__water_distance) gives a shelter or
-- campsite `water_distance_ft`, CSI's figure in ATC's own feet, and beside it
-- `water_distance_source`, CSI's Nearest_Water_Source verbatim (#1728): 42 of
-- the 305 distances are OSA_Field_Estimate, a steward's round number, and the
-- phone prints those with a tilde. A row the file gives no distance gets
-- neither column (export_poi.py's load_water_distances() and
-- attach_water_distance()), and an empty provenance is no provenance. The
-- join is on the published id, `atc_shelters:` or `atc_campsites:` and the
-- GlobalID, as the Python's is, after the ledger has resolved ids.
--
-- THE SYNTHESIZED WATER POINT (#694, synthesize_csi_water()). CSI says how
-- FAR water is and never WHERE, so a site whose card promises water nearby
-- gets a water POI at its anchor's coordinates, riding the site as a member
-- and drawing no pin of its own. It is made for every shelter or campsite
-- that is not itself a member of a site, carries a distance no further than
-- the widest site radius (lib/poi_sites.py's 150 m, in feet: the same gate
-- the nearby line uses, so a member exists for every card that promises
-- water and for none that does not), and has no real water point in its
-- site. A lone anchor becomes a two-part site. The point is low confidence,
-- carries the anchor's distance and provenance, publishes as
-- `atc_csi:<GlobalID>` resolved through the ledger like every other id, and
-- its description says whose figure it is (the poi_water_claims seed) and
-- that the spot is unmapped.
with sites as (
    select * from {{ ref('int_points_of_interest__sites') }}
),

distances as (
    select
        case layer
            when 'shelters' then 'atc_shelters:'
            when 'campsites' then 'atc_campsites:'
        end || atc_global_id as poi_id,
        distance_ft,
        nullif(provenance, '') as provenance
    from {{ ref('base_atc__water_distance') }}
    where
        distance_ft is not null
        and layer in ('shelters', 'campsites')
),

claims as (
    select * from {{ ref('poi_water_claims') }}
),

live_ledger as (
    select
        poi_id,
        source_feature_id
    from {{ ref('base_ourhike__poi_identity') }}
    where
        retired is null
        and source = 'atc_csi'
),

with_distance as (
    select
        sites.*,
        cast(sites.file_order as bigint) * 1000000000
        + coalesce(sites.source_row, 0) as record_order,
        case
            when sites.phone_files = 'poi_by_type' then distances.distance_ft
        end as water_distance_ft,
        case
            when sites.phone_files = 'poi_by_type' then distances.provenance
        end as water_distance_source
    from sites
    left join distances on sites.poi_id = distances.poi_id
),

sites_with_real_water as (
    select distinct site_id
    from with_distance
    where
        site_role = 'member'
        and poi_type = 'water'
        and source != 'atc_csi'
),

synthesis_anchors as (
    select with_distance.*
    from with_distance
    where
        with_distance.phone_files = 'poi_by_type'
        and with_distance.poi_type in ('shelter', 'campsite')
        and coalesce(with_distance.site_role, '') != 'member'
        and with_distance.water_distance_ft is not null
        and with_distance.water_distance_ft
        <= {{ var('poi_site_name_radius_m') }}
        / {{ var('poi_metres_per_foot') }}
        and coalesce(with_distance.site_id, '') not in (
            select sites_with_real_water.site_id from sites_with_real_water
        )
),

anchored as (
    -- A lone anchor becomes a two-part site: the glyph and the chip both hang
    -- off site properties, and the anchor may not have had any.
    select
        with_distance.poi_id,
        with_distance.poi_key,
        with_distance.source_key,
        with_distance.file_order,
        with_distance.source_row,
        with_distance.club,
        with_distance.source,
        with_distance.phone_files,
        with_distance.trail_id,
        with_distance.source_feature_id,
        with_distance.source_feature_id_json,
        with_distance.derived_id,
        with_distance.name,
        with_distance.poi_type,
        with_distance.confidence,
        with_distance.confidence_floor,
        with_distance.asset,
        with_distance.facility,
        with_distance.lon,
        with_distance.lat,
        with_distance.properties,
        with_distance._loaded_at,
        with_distance.not_on_at,
        case
            when synthesis_anchors.poi_id is not null
                then coalesce(with_distance.site_id, with_distance.poi_id)
            else with_distance.site_id
        end as site_id,
        case
            when synthesis_anchors.poi_id is not null
                then coalesce(with_distance.site_role, 'anchor')
            else with_distance.site_role
        end as site_role,
        case
            when
                synthesis_anchors.poi_id is not null
                and with_distance.site_id is null
                then with_distance.name
            else with_distance.site_name
        end as site_name,
        with_distance.record_order,
        with_distance.water_distance_ft,
        with_distance.water_distance_source,
        cast(null as varchar) as synthesized_description
    from with_distance
    left join
        synthesis_anchors
        on with_distance.poi_id = synthesis_anchors.poi_id
),

synthesized as (
    select
        coalesce(live_ledger.poi_id, 'atc_csi:' || anchor.source_feature_id)
            as poi_id,
        {{ dbt_utils.generate_surrogate_key(["'atc_csi'", 'anchor.poi_key']) }}
            as poi_key,
        anchor.source_key,
        99 as file_order,
        anchor.source_row,
        anchor.club,
        'atc_csi' as source,
        anchor.phone_files,
        anchor.trail_id,
        anchor.source_feature_id,
        to_json(anchor.source_feature_id) as source_feature_id_json,
        'atc_csi:' || anchor.source_feature_id as derived_id,
        case
            when coalesce(anchor.name, '') != ''
                then 'Water near ' || anchor.name
            else 'Water'
        end as name,
        'water' as poi_type,
        'low' as confidence,
        cast(null as varchar) as confidence_floor,
        cast(null as varchar) as asset,
        cast(null as varchar) as facility,
        anchor.lon,
        anchor.lat,
        cast('{}' as json) as properties,
        anchor._loaded_at,
        -- Never marked off the A.T.: it sits on an ATC shelter or campsite.
        cast(null as varchar) as not_on_at,
        coalesce(anchor.site_id, anchor.poi_id) as site_id,
        'member' as site_role,
        case
            when anchor.site_id is null then anchor.name
            else anchor.site_name
        end as site_name,
        99000000000 + anchor.record_order as record_order,
        anchor.water_distance_ft,
        anchor.water_distance_source,
        replace(
            coalesce(claim.claim, fallback.claim),
            '{placed_on}',
            case
                when coalesce(anchor.name, '') != '' then anchor.name
                else 'the ' || anchor.poi_type
            end
        )
        || '; the spot itself is not mapped, so this point sits on the '
        || anchor.poi_type
        || '.' as synthesized_description
    from synthesis_anchors as anchor
    left join claims as claim on anchor.water_distance_source = claim.provenance
    left join claims as fallback on fallback.provenance = '*'
    left join
        live_ledger
        on anchor.source_feature_id = live_ledger.source_feature_id
)

select
    poi_id,
    poi_key,
    source_key,
    file_order,
    source_row,
    club,
    source,
    phone_files,
    trail_id,
    source_feature_id,
    source_feature_id_json,
    derived_id,
    name,
    poi_type,
    confidence,
    confidence_floor,
    asset,
    facility,
    lon,
    lat,
    properties,
    _loaded_at,
    not_on_at,
    site_id,
    site_role,
    site_name,
    record_order,
    water_distance_ft,
    water_distance_source,
    synthesized_description
from anchored
union all
select
    poi_id,
    poi_key,
    source_key,
    file_order,
    source_row,
    club,
    source,
    phone_files,
    trail_id,
    source_feature_id,
    source_feature_id_json,
    derived_id,
    name,
    poi_type,
    confidence,
    confidence_floor,
    asset,
    facility,
    lon,
    lat,
    properties,
    _loaded_at,
    not_on_at,
    site_id,
    site_role,
    site_name,
    record_order,
    water_distance_ft,
    water_distance_source,
    synthesized_description
from synthesized
