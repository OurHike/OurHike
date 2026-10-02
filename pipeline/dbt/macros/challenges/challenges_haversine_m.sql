{#-
    lib/challenges.py's haversine_m(): great-circle metres between two
    lon/lat points, the formula the client's lib/trailPosition.ts also uses
    (`haversineFeet`), with lib/challenges.py's radius of 6,371,008.8 m.

    Written as the Python is, operation for operation: each latitude to
    radians before the difference (dphi = phi2 - phi1), and radians() as
    CPython's x * (pi / 180), so a vertex distance here is the Python's to
    the last bit wherever the two libms agree (Reasoned, not measured).

    Not EPSG:5070, on purpose. pipeline/ELT.md measures new thresholds in
    EPSG:5070, never with ST_Distance_Sphere on (lon, lat), and this is
    neither: it is the metric the radius was written against and the phone
    reads, where EPSG:5070 is direction-dependent (measured 2026-10-02 at
    41 N 74 W: a 30.0 m east-west pair read 29.83 m, a north-south one
    30.21 m).
-#}
{%- macro challenges_haversine_m(lon1, lat1, lon2, lat2) -%}
    (
        2 * 6371008.8 * asin(sqrt(
            power(sin((({{ lat2 }}) * (pi() / 180.0) - ({{ lat1 }}) * (pi() / 180.0)) / 2), 2)
            + cos(({{ lat1 }}) * (pi() / 180.0)) * cos(({{ lat2 }}) * (pi() / 180.0))
            * power(sin(((({{ lon2 }}) - ({{ lon1 }})) * (pi() / 180.0)) / 2), 2)
        ))
    )
{%- endmacro -%}
