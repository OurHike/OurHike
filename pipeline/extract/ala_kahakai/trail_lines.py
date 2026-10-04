"""Ala Kahakai Trail Association: trail lines, drawn from nps/'s resources (decision 34), registered on
2026-10-03.

The official geometry is a corridor polygon, not a line

The association's own map, ALKA-MAP.pdf (decision 54's wave 4, read 2026-10-04), is one page of two
images and no text layer: a picture of the trail, which no reader can take a line from.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "Live read 2026-10-03 (decision 54, wave 1): `nps_ala_kahakai_kohala_hema` (14 lines), "
        "`nps_ala_kahakai_alanui_aupuni` (1 line), `nps_ala_kahakai_kaawaloa` (1 line), "
        "`nps_ala_kahakai_kiholo_puako` (2 lines) registered in sources.json and extracted in "
        "nps/trail_lines.py.",
        "`NPSAGOL/Ala_Kahakai_National_Historic_Trail_Official_Corridor/0`: 1 polygon (corridor, "
        "2025-12-05). `NPSAGOL/ALKA_Story_Maps`: lines Kohala Hema 14, Alanui Aupuni 1, Kaʻawaloa 1, "
        'Kīholo–Puakō 2. `nps_trails`: KAHO "Ala Kahakai Trail" 4 (LOADED fragment). Own: '
        "`https://www.alakahakaitrail.org/s/ALKA-MAP.pdf` (PDF)",
        "GET 2026-10-04 under lib/user_agent.py's agent, after robots.txt (Squarespace's; /s/ is not disallowed): "
        "ALKA-MAP.pdf, application/pdf, 3,444,065 bytes, 1 page, 2 images, 0 characters of text to pypdf",
    ),
    where=(
        "https://www.alakahakaitrail.org/s/ALKA-MAP.pdf",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ALKA_Story_Maps/FeatureServer/0",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ALKA_Story_Maps/FeatureServer/1",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ALKA_Story_Maps/FeatureServer/2",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ALKA_Story_Maps/FeatureServer/3",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
