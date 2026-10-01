"""The trail_orgs.json rows that get no club folder, one dated line each (decision 18).

Twelve national umbrellas and thirteen route-only trails, counted 2026-10-01:
each publishes through somebody else, so there is nothing of its own to
extract. An umbrella's reason is its trail_orgs.json `why`, quoted. A
route-only trail's is the same for all thirteen, so it is written once here
rather than copied with the route authors' names some of those rows carry.
The aggregators (osm, outerspatial, avenza) are not here: each has a
_shared/ folder. tests/test_extract_layout.py holds every umbrella and
route-only slug to exactly one line.
"""

from datetime import date

from extract._contract import NotClub

CONFIRMED = date(2026, 10, 1)
ROUTE_ONLY = (
    "a route stitched across trails other organizations maintain, with no maintaining organization and no geometry "
    "of its own (trail_orgs.json's `why`); its trails come through their stewards' folders"
)

NOT_CLUBS = {
    "american-hiking": NotClub(
        "national_umbrella", CONFIRMED, "Advocacy and volunteer mobilisation; maintains no trail of its own."
    ),
    "pnts": NotClub(
        "national_umbrella", CONFIRMED, "Coordinates the NST and NHT nonprofits. Its members hold the data; it holds none."
    ),
    "sca": NotClub("national_umbrella", CONFIRMED, "Crews maintain trails on partner land. The partner holds the geometry."),
    "conservation-legacy": NotClub(
        "national_umbrella", CONFIRMED, "Conservation corps. Same shape as the SCA — crews, not datasets."
    ),
    "bcha": NotClub("national_umbrella", CONFIRMED, "Stock-based volunteer maintenance on other people's trails."),
    "imba": NotClub(
        "national_umbrella",
        CONFIRMED,
        "Advocacy. Mountain-bike geometry generally sits in Trailforks, which is restricted and is not this app's subject.",
    ),
    "lnt": NotClub(
        "national_umbrella",
        CONFIRMED,
        "Education and ethics organisation. Maintains no trail and holds no geometry - recorded so that a future survey does not spend a search on it.",
    ),
    "tpl": NotClub(
        "national_umbrella", CONFIRMED, "Acquires land along trails, including for the PCT. Project GIS is not a trail dataset."
    ),
    "lta": NotClub(
        "national_umbrella",
        CONFIRMED,
        "Coordinates the land trusts, several of which do hold trails; the Alliance itself holds none. The member trusts are the rows worth chasing, and three of them are already here.",
    ),
    "atra": NotClub(
        "national_umbrella",
        CONFIRMED,
        "Race sanctioning and advocacy for trail running. Maintains no trail and publishes no geometry; the trails its races use belong to the land managers already in this file.",
    ),
    "american-trails": NotClub(
        "national_umbrella",
        CONFIRMED,
        "The National Recreation Trails directory at americantrails.org lists trail names and the agencies behind them; it publishes no centerline geometry. Useful to a researcher filling in this catalogue's 51 endpointless rows, useless to a map, so it carries no endpoint rather than a URL that would read like one.",
    ),
    "rtc": NotClub(
        "national_umbrella",
        CONFIRMED,
        "Licensed by negotiated agreement and the basis of a commercial bike layer. A stated restriction, so the assume-open default does not reach it.",
        terms="custom, by agreement",
    ),
    "hayduke": NotClub("route_only", CONFIRMED, ROUTE_ONLY),
    "sierra-high": NotClub("route_only", CONFIRMED, ROUTE_ONLY),
    "lowest-highest": NotClub("route_only", CONFIRMED, ROUTE_ONLY),
    "se-serpentine": NotClub("route_only", CONFIRMED, ROUTE_ONLY),
    "hot-springs": NotClub("route_only", CONFIRMED, ROUTE_ONLY),
    "ect": NotClub("route_only", CONFIRMED, ROUTE_ONLY),
    "big-seki": NotClub("route_only", CONFIRMED, ROUTE_ONLY),
    "solomons": NotClub("route_only", CONFIRMED, ROUTE_ONLY),
    "sky-islands": NotClub("route_only", CONFIRMED, ROUTE_ONLY),
    "nnm-loop": NotClub("route_only", CONFIRMED, ROUTE_ONLY),
    "get": NotClub("route_only", CONFIRMED, ROUTE_ONLY),
    "mogollon": NotClub("route_only", CONFIRMED, ROUTE_ONLY),
    "ahr": NotClub("route_only", CONFIRMED, ROUTE_ONLY),
}
