{#-
    A line's length in metres along the WGS84 ellipsoid, for a line held in
    EPSG:5070: the trail graph's published edge lengths (decision 90, the
    maintainer's poll of 2026-10-06, answering DBT2-2: "geodesic length on
    WGS84 in the dbt model and in build_trail_graph.py").

    EPSG:5070 is equal-area for the lower 48 only, and its metre is not the
    ground's. A kilometre on the ellipsoid reads, in EPSG:5070 (measured
    2026-10-06 with pyproj): north-south 1,008.0 m at Harriman, 887.7 m at
    Anchorage, 775.9 m in the Brooks Range and 755.7 m in American Samoa;
    east-west 992.0 m at Harriman and 1,126.4 m at Anchorage. The graph is
    still noded in EPSG:5070, whose metres its tolerances are written in.

    ST_Length_Spheroid reads x as latitude (the dbt skill's trap), so the
    line goes back to lon/lat and is flipped first. Unflipped, the Anchorage
    kilometre reads NaN and the Harriman one 1,331.6 m. Flipped, every
    kilometre above read pyproj's Geod(ellps='WGS84') length, and
    build_trail_graph.py's, to within 1e-8 m on DuckDB 1.5.5 (2026-10-06);
    tests/test_dbt_trail_network_parity.py holds it to a micrometre.
-#}
{% macro geodesic_length_m(geom_5070) -%}
    st_length_spheroid(
        st_flipcoordinates(
            st_transform({{ geom_5070 }}, 'EPSG:5070', 'EPSG:4326', always_xy := true)
        )
    )
{%- endmacro %}
