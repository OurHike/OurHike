"""FLTC's Waypoints layer, the one its own map at fingerlakestrail.org/map/ draws.

Read live 2026-10-03 for decision 54's wave 1. The same Experience Builder app names FLTC's
Closures_, Hunting_Bypasses_ and Temporary_Notices layers, which are notices (decision 53) rather than
points of interest, and FLTmain, the trail line: none of them is this file's. This layer's own 76
hunting closures and 7 high-water hazards are notices too, which sources.json's fltc_waypoints row
says so that a POI mapping leaves them out. fingerlakestrail.org's robots.txt disallows /REF/ and
/FLTC/; nothing under either was fetched.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("fltc_waypoints",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
