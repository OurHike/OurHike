"""E Mau Na Ala Hele: places, drawn from nps/'s resources, and the rest not landed (decision 54, wave 1,
read 2026-10-03).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via nps `nps_park_boundaries` (the KAHO, PUHO and PUHE units), registered 2026-10-03.",
        "Not landed: Hawaii Statewide GIS's State Parks (Infrastructure/MapServer/16), Reserves "
        "(Terrestrial/MapServer/1), County Parks (Infrastructure/MapServer/17) and Ahupuaʻa "
        "(HistoricCultural/MapServer/1), whose steward, the State of Hawaii, has no folder (decision 54's wave 6).",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/NPS_Land_Resources_Division_Boundary_and_Tract_Data_Service/FeatureServer/2",
        "https://emaunaalahele.org/",
    ),
    reason="partly drawn from nps/'s resources (decision 34); Hawaii Statewide GIS's layers wait for a folder (wave 6)",
)
