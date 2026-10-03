"""Monadnock-Sunapee Greenway Trail Club: places, drawn from nh_granit/'s resources (decision 54, wave 1,
read 2026-10-03).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via nh_granit `nh_conservation_lands` (EC/Conservation/MapServer/0, 13,502 polygons), registered 2026-10-03: the"
        " 33 parcels the coverage audit found within 10 m of the Greenway's segments (Pillsbury and Mount Sunapee state "
        "parks, Monadnock Reservation and the rest) are among them. Layer 6, which the audit read, is the same rows "
        "(nh_granit's SAME_AS note).",
    ),
    where=("https://nhgeodata.unh.edu/nhgeodata/rest/services/EC/Conservation/MapServer/0",),
    reason=(
        "drawn from nh_granit/'s resources, extracted once there (decision 34); checked names the layer this org's data "
        "arrives in"
    ),
)
