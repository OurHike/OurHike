"""Adirondack Mountain Club: places, refused by ADK's terms (decision 54, wave 5). Its places pages (the
Adirondak Loj property, the High Peaks Information Center, Johns Brook Lodge, the Loj's hiker parking) are
prose about places it runs, and ADK's terms forbid access through automated or non-human means, quoted in
`terms` as adk/closures.py records them (decision 53's inventory, 2026-10-03). Not fetched; held until ADK
permits, the maintainer's request to send.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "adk/closures.py's refusal, read 2026-10-03 at https://adk.org/terms-conditions/ ('Last updated August 12, "
        "2026'); nothing on adk.org was requested for this note.",
        "the coverage audit (2026-10-01, batch c4_regional_1): /explore/adk-loj-property/, "
        "/explore/high-peaks-information-center/, /explore/johns-brook-lodge/, "
        "/tips-for-hiker-parking-adirondak-loj/, pages gated by the terms.",
    ),
    where=(
        "https://adk.org/terms-conditions/",
        "https://adk.org/",
    ),
    terms=(
        'https://adk.org/terms-conditions/, §3 User Representations, as adk/closures.py quotes it: "By using the '
        "Services, you represent and warrant that: ... (5) you will not access the Services through automated or "
        'non-human means, whether through a bot, script or otherwise".'
    ),
    reason="refused: ADK's terms forbid access through automated or non-human means (quoted in `terms`); held until ADK permits",
)
