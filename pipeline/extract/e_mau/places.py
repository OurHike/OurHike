"""E Mau Na Ala Hele: places, published, and not landed (coverage audit 2026-10-01, batch p01_persist).

Licence: State Parks and County Parks: open_licence, public domain (State of Hawaii Terms of Use,
quoted in the POI row). Reserves: "No warranty is made that the GIS data… will be error free… The
features are graphic representation of managed areas for planning purposes…", a disclaimer …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Inside the ALKA corridor, from Hawaii Statewide GIS:",
        "State Parks (`Infrastructure/MapServer/16`): 14 (shp 4, sra 3, sm 2, sp 2…), including Kīholo SPR.",
        "Reserves (`Terrestrial/MapServer/1`): 29.",
        "County Parks, Hawaii County (`Infrastructure/MapServer/17`): 64 (owner Govt. State 35, County 25).",
        "Ahupuaʻa (`HistoricCultural/MapServer/1`): 147 (Kona 67, Kohala 40, Kaʻū 31, Puna 9).; Statewide "
        "totals: State Parks 70, Reserves 381, County Parks (Hawaii Co.) 286, Ahupuaʻa 727.; NPS unit "
        "boundaries for KAHO, PUHO and PUHE are in `nps/`.; Tried: 1–6 above.",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://emaunaalahele.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
