# mapbuild — how the map-*.svg frames were made

    npm install            # us-atlas, world-atlas, topojson-client, topojson-simplify, d3-geo
    # put the trail line at src/at-osm.geojson (OSM relation 156553 as a LineString, ODbL)
    node build2.mjs 358 400 m2-line.json 900
    node build2.mjs 358 360 m2-where.json 900
    node build2.mjs 358 330 m2-welcome.json 900
    node build2.mjs 420 470 m2-poster.json 1100
    python3 -I assemble2.py    # writes map-phone/where/welcome/poster.svg

The trail line is NOT in this folder (ODbL; the build uses the pipeline's published
centerline instead). Miles are placed proportionally along the line (@unvalidated).
The colours and the diamond pin are OurHike's own — see the brief, "The map: reuse".
