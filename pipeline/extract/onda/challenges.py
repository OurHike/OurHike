"""Oregon Natural Desert Association: challenges, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

Page. Skeptic: the page (created 2019-03-15, modified 2022-12-02) still reads as open: "There are
50+ miles of trails in Badlands. Can you hit them all?". But the post `/we-challenged-you-hiked/`
calls it "a six-month-long exploration challenge" for the wilderness's tenth anniversary. Whether it
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`/badlands-challenge/` (2019): hike the Badlands Wilderness trails (more than 50 mi), then email a trip log.",),
    where=("https://onda.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
