"""Ozark Trail Association: closures, from the 'Trail Conditions' block of each of the trail's 14 section pages,
hourly (decision 53 phase B and decision 55, 2026-10-03).

Each section page is one PageNotice (extract/_notices.py) read through its WordPress REST route,
`/wp-json/wp/v2/pages/<id>`, which carries no query string; each is its own registry row, because a
builder takes one key and one key is one upstream page. All 14 were read live under our agent on
2026-10-03 after ozarktrail.com's robots.txt (WooCommerce and /wp-admin/ paths only, no Crawl-delay),
and each lands its title, its own modified_gmt as the date (2025-01-01 to 2026-01-16 that day), a hash
of the rendered content and the link. The blocks stamp their own months ('4/2025 Trail Update'), which
are not read: a month is not a day. Current River's block reads 'Midco Hollow south to Pike Creek
Road—will remain closed due to unprecedented tornado damage'.

The 14 are the pages decision 53's inventory listed with a 'Trail Conditions' block (batch 5); the
coverage audit found the block on 13 of 14 (2026-10-01). Reading the site's whole pages route as one
WordpressPosts table instead would be one request an hour rather than 14, but would land all 70 pages'
bodies in the raw store, and a site's other pages are where people's names and numbers usually sit
(Reasoned; the other 56 were not read). Decision 59 leaves such a column out whole, so the 14 page
reads, which land no text at all, are the ones taken.

OTA's terms restrict reproduction ("Reproduction is prohibited other than in accordance with the
copyright notice"), which is decision 55's case: facts and a link, the terms quoted on each row.

The blocks are closures and warnings both (a tornado closure beside stinging nettle and car break-ins),
split in dbt (decision 7), so warnings.py shares this file.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
c7_regional_4): "Pages. No feed: `posts` holds 13 items in 4 categories, none of them conditions."
"""

from extract._kinds import page_notice

# Registry key -> the section page's WordPress id (read 2026-10-03; each row's notes name the page).
SECTION_PAGES = {
    "ota_current_river_conditions": 42254,
    "ota_upper_current_river_conditions": 42332,
    "ota_eleven_point_conditions": 2678,
    "ota_victory_conditions": 42311,
    "ota_wappapello_conditions": 42312,
    "ota_north_fork_conditions": 42309,
    "ota_between_the_rivers_conditions": 42223,
    "ota_blair_creek_conditions": 2639,
    "ota_karkaghne_conditions": 42294,
    "ota_taum_sauk_conditions": 42300,
    "ota_middle_fork_conditions": 42308,
    "ota_courtois_conditions": 42207,
    "ota_trace_creek_conditions": 42310,
    "ota_marble_creek_conditions": 42307,
}

CLAIMS = tuple(SECTION_PAGES)
RESOURCES = [page_notice(key, wp_page=page_id) for key, page_id in SECTION_PAGES.items()]
