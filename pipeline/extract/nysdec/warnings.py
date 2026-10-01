"""DEC's warnings: fire danger is Mesonet's under a no-redistribution policy, and the hunting and algal-bloom layers are not landed."""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "fire danger: NYS Mesonet's GetFDRA JSON, 12 Fire Danger Rating Areas with risk and validity dates, "
        "embedded in DEC's fire-danger map; no FDRA polygons were found",
        "hunting seasons by Wildlife Management Unit: big_game_CopyFeatures/FeatureServer/0, 92 polygons, last edited 2026-09-11",
        "harmful algal bloom reports: Current_HAB_Reports_DIL/FeatureServer/0",
    ),
    where=(
        "https://api.nysmesonet.org/data/firewx/GetFDRA/",
        "https://dec.ny.gov/environmental-protection/wildfires/fire-danger-map",
        "https://services6.arcgis.com/DZHaqZm9cxOD4CWM/arcgis/rest/services/Current_HAB_Reports_DIL/FeatureServer/0",
    ),
    terms=(
        'NYS Mesonet Data Access Policy: no redistribution "without the express prior written consent of RFSUNY" '
        "(the fire-danger feed; the two DEC layers carry no such text)"
    ),
    reason=(
        "the two DEC layers are not landed: neither has a sources.json row, and whether hunting seasons and "
        "algal blooms are warnings at all is an open question for the maintainer"
    ),
)
