{#-
    The rows of `relation` whose geometry reaches outside the box its source
    publishes in: the lon/lat swap test. A swapped point in the eastern
    United States (lon -74, lat 41 read as lon 41, lat -74) is still inside
    +/-180 and +/-90, so the range tests every geometry mart carries pass it
    (assert_pois_land_in_the_region_this_build_covers.sql's header has the
    green build that let one through). The generic test
    lands_in_the_region_its_source_publishes_in and that POI test both call
    this, so the boxes have one home.

    `geometry` is a SQL expression for the row's GEOMETRY. Its bounding box
    must sit inside the box `regions` gives its `source_key_column`, and a
    key it does not list gets `eastern`.

    THE BOXES, and what each rests on (extents measured 2026-10-03 from each
    live ArcGIS layer's returnExtentOnly, in lon/lat):
    - eastern, lat 30 to 50 and lon -90 to -66: the A.T. from Georgia to
      Maine and the New York, New Jersey, Pennsylvania, Connecticut,
      Massachusetts and North Carolina layers. Every ATC, OPRHP, NYNJTC,
      Mohonk, DEC, NJDEP, PASDA, CT DEEP, NC MST and MassGIS layer measured
      inside it, the widest lat 34.53 to 45.93 and lon -84.48 to -68.71.
    - national, lat 18 to 72 and lon -180 to -64: the fifty states, with no
      room for a swapped U.S. point (its latitude would be -64 or less).
      The western and nationwide trail layers listed measured inside it.
    - us_and_territories, lat -20 to 72 at any longitude: for a layer that
      reaches American Samoa or Guam. NPS's trails measured lat -14.37 to
      65.85 and lon -170.77 to 145.73. A swap is still caught: a point that
      survives the +/-180 test transposed had a longitude of -90 to -64, so
      its latitude now reads -64 or less. NWS's alerts get it because they
      follow the weather squares onto every published trail, Puerto Rico's
      (USFS, lat 18.27) among them, and an alert there reaches the south
      coast below lat 18.

    DECISION 54'S TRAIL-LINE ROWS (2026-10-03) are listed after
    wi_ice_age_trail, each by the extent on its own sources.json row: the
    layer's returnExtentOnly in EPSG:4326, or, for usfws_trail_segments, whose
    returnExtentOnly answer (lat -24.99 to 90) no vertex bears out, every
    vertex (lat 13.64 to 63.20, lon -159.48 to 144.87, Guam and Puerto Rico
    the outliers). A row whose extent sits inside the eastern box has no
    entry.

    DECISION 54'S POINT-OF-INTEREST ROWS (2026-10-03) are listed after
    nws_alerts, each by its vertices: every point of the layer, read that
    day with outSR 4326 and geometry only, never the server's extent. A
    point row whose points all sit inside the eastern box has no entry, as
    GMC's, FLTC's, AMC's, CFPA's, NJDEP's and the Smokies' shelters do. The
    widest: nps_points_of_interest, lat -14.29 to 68.14 and lon -170.71 to
    145.73 (American Samoa to Guam), and blm_recreation_sites, lat 26.95 to
    69.57. IATA's reach lon -92.67 in western Wisconsin and FTA's lat 25.86
    at the Florida Trail's southern end, both outside the eastern box.

    The second batch of point rows follows, the same way: USGS's trailheads,
    ranger stations and GNIS springs and both USFWS layers reach the
    territories (usfws_refuge_property_points lon -177.38 to 179.29, the
    Pacific refuges either side of the antimeridian), and TDEC's three
    Tennessee State Parks layers reach lon -90.13 near Memphis.

    @unvalidated Every margin is picked, not measured. What would settle it
    is the per-club box from trail_orgs.json's `states` that pipeline/ELT.md
    plans. A source loading outside the eastern box without a row in
    `regions` fails here: that is the design, since widening a safety bound
    is part of registering a source.
-#}
{% macro lands_outside_its_region(
    relation, geometry, source_key_column='source_key'
) %}

{%- set boxes = {
    'eastern': (30.0, 50.0, -90.0, -66.0),
    'national': (18.0, 72.0, -180.0, -64.0),
    'us_and_territories': (-20.0, 72.0, -180.0, 180.0),
} -%}
{%- set regions = {
    'usfs_trails': 'national',
    'usfs_rec_sites': 'national',
    'blm_trails': 'national',
    'cotrex_trails': 'national',
    'wa_rco_trails': 'national',
    'utah_sgid_trails': 'national',
    'ncta_trail': 'national',
    'alaska_trails': 'national',
    'azgeo_arizona_trail': 'national',
    'tahoe_rim_trail': 'national',
    'duluth_superior_hiking_trail': 'national',
    'pcta_centerline': 'national',
    'cdtc_centerline': 'national',
    'wi_ice_age_trail': 'national',
    'nps_oregon_nht': 'national',
    'nps_california_nht': 'national',
    'nps_old_spanish_nht': 'national',
    'nps_el_camino_tejas_nht': 'national',
    'nps_pony_express_nht': 'national',
    'nps_mormon_pioneer_nht': 'national',
    'nps_santa_fe_nht': 'national',
    'nps_trail_of_tears_nht': 'national',
    'nps_el_camino_tierra_adentro_nht': 'national',
    'nps_butterfield_overland_nht': 'national',
    'nps_butterfield_srs_route': 'national',
    'nps_lewis_clark_nht': 'national',
    'nps_lewis_clark_water_trails': 'national',
    'nps_ala_kahakai_kohala_hema': 'national',
    'nps_ala_kahakai_alanui_aupuni': 'national',
    'nps_ala_kahakai_kaawaloa': 'national',
    'nps_ala_kahakai_kiholo_puako': 'national',
    'nps_anza_recreation_trails': 'national',
    'nps_anza_nht': 'national',
    'blm_old_spanish_nht_trails': 'national',
    'blm_old_spanish_nht_alignment': 'national',
    'blm_iditarod_nht': 'national',
    'usfs_pacific_northwest_trail': 'national',
    'ata_arizona_trail': 'national',
    'ata_mountain_bike_passages': 'national',
    'ttc_butler_trail': 'national',
    'austin_pard_trails': 'national',
    'des_moines_trails': 'national',
    'iowa_dnr_state_park_trails': 'national',
    'tdec_state_park_trails_2024': 'national',
    'tdec_public_trails_view': 'national',
    'tdec_public_trails': 'national',
    'portland_parks_trails': 'national',
    'ppr_trails': 'national',
    'oregon_metro_trails': 'national',
    'ncta_spurs': 'national',
    'ncta_nearby_trails': 'national',
    'ncta_superior_hiking_trail': 'national',
    'octa_hastings_cutoff_route': 'national',
    'octa_naches_pass_trail': 'national',
    'octa_natcon_boardman_tracks_2016': 'national',
    'octa_corral_springs_tracks_2015': 'national',
    'octa_whitman_longsegs_2020': 'national',
    'octa_polylines_oregon_trail_kml': 'national',
    'octa_lockhart_trail_route': 'national',
    'octa_barlow_road_62': 'national',
    'octa_barlow_road_63': 'national',
    'octa_barlow_road_64': 'national',
    'octa_barlow_road_65': 'national',
    'octa_barlow_road_86': 'national',
    'octa_molalla_young_trail_62': 'national',
    'octa_molalla_young_trail_63': 'national',
    'octa_klamath_fremont_trail_65': 'national',
    'octa_klamath_fremont_trail_71': 'national',
    'octa_meek_trail_65': 'national',
    'octa_meek_trail_71': 'national',
    'octa_meek_trail_86': 'national',
    'octa_oregon_trail_71': 'national',
    'octa_oregon_trail_81': 'national',
    'octa_oregon_trail_85': 'national',
    'octa_oregon_trail_86': 'national',
    'octa_oregon_trail_87': 'national',
    'octa_oregon_trail_88': 'national',
    'octa_oregon_trail_89': 'national',
    'octa_bonneville_trail_1834_86': 'national',
    'onda_odt_tracks': 'national',
    'ridgetrail_official_route': 'national',
    'sbts_maintained': 'national',
    'shta_line_2025': 'national',
    'shta_spurs_and_loops': 'national',
    'shta_spirit_mountain_spur_2025': 'national',
    'lake_county_superior_hiking_trail': 'national',
    'tko_oregon_coast_trail': 'national',
    'tpwd_state_park_trails': 'national',
    'usace_tulsa_trails': 'national',
    'usfws_trail_segments': 'us_and_territories',
    'nps_trails': 'us_and_territories',
    'nws_alerts': 'us_and_territories',
    'nps_points_of_interest': 'us_and_territories',
    'blm_recreation_sites': 'national',
    'ncta_points': 'national',
    'alaska_trails_cabins_and_campsites': 'national',
    'alaska_trails_access_points': 'national',
    'tahoe_rim_water_sources': 'national',
    'tahoe_rim_campgrounds': 'national',
    'tahoe_rim_points_of_interest': 'national',
    'tahoe_rim_trailheads': 'national',
    'pcta_halfmile_water_sources': 'national',
    'pcta_halfmile_campsites': 'national',
    'pcta_trailheads': 'national',
    'cdtc_water_caches': 'national',
    'cdtc_bootheel_water_caches': 'national',
    'cdtc_parking': 'national',
    'cdtc_trailheads_and_mail': 'national',
    'fta_campsites': 'national',
    'fta_trailheads': 'national',
    'iata_water': 'national',
    'iata_camping': 'national',
    'iata_parking': 'national',
    'usgs_structures_campgrounds': 'national',
    'usgs_structures_trailheads': 'us_and_territories',
    'usgs_structures_cabins': 'national',
    'usgs_structures_shelters': 'national',
    'usgs_structures_ranger_stations': 'us_and_territories',
    'usgs_gnis_springs': 'us_and_territories',
    'cotrex_trailheads': 'national',
    'cpw_facilities': 'national',
    'utah_trailheads': 'national',
    'utah_state_park_campsites': 'national',
    'utah_highest_peaks': 'national',
    'black_hills_trailheads': 'national',
    'black_hills_parking': 'national',
    'sbts_connected_community_trailheads': 'national',
    'ridgetrail_campsites': 'national',
    'usfws_refuge_property_points': 'us_and_territories',
    'usfws_refuge_access_points': 'us_and_territories',
    'tn_state_parks_hiking_assets': 'national',
    'tn_state_parks_campgrounds': 'national',
    'tn_state_parks_campsites': 'national',
} -%}

with placed as (
    select
        {{ source_key_column }} as source_key,
        {{ geometry }} as geom
    from {{ relation }}
),

boxed as (
    select
        source_key,
        st_xmin(geom) as xmin,
        st_xmax(geom) as xmax,
        st_ymin(geom) as ymin,
        st_ymax(geom) as ymax,
        case
            {% for key, region in regions.items() -%}
            when source_key = '{{ key }}' then '{{ region }}'
            {% endfor -%}
            else 'eastern'
        end as region
    from placed
    where geom is not null
)

select *
from boxed
where
    case region
        {% for region, box in boxes.items() -%}
        when '{{ region }}'
            then
                ymin < {{ box[0] }} or ymax > {{ box[1] }}
                or xmin < {{ box[2] }} or xmax > {{ box[3] }}
        {% endfor -%}
    end

{% endmacro %}
