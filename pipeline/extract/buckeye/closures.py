"""Buckeye Trail Association: closures, 26 notice sources read here (decision 53 phase B, 2026-10-03).

- `bta_section_<part>`, 26 sources, the Buckeye Trail's 26 sections, in the order
  https://buckeyetrail.org/sections lists them: one notice for the page (PageNotice) each. One of
  the 26 section pages buckeyetrail.org/sections lists; each carries that section's Trail Alerts and
  Map Updates. The /hike/alerts hub lists none of them. buckeye is one of the four `refuse`
  organizations, so these rows never publish until its permission is recorded (rule 7), whatever
  decision 55 says of its terms. Read daily: one of 26 Buckeye Trail section pages on one host, from
  a `refuse` organization whose rows cannot publish until its permission is recorded (ELT.md, 'Who
  may publish', rule 7); read daily, so the club's site is asked 26 times a day rather than 624 for
  rows no hiker can see yet.

Not read: https://buckeyetrail.org/hike/alerts, the 'Trail Alerts and Map Updates' hub, which held
only guidance text and no item on 2026-10-03. Every section page names its Trail Alerts by BTA's own
'Points' (PT 10-11), which place a notice only with BTA's point data, unreviewed. The terms restrict
downloading any portion without written consent and do not forbid reading, so decision 55 names
Buckeye among the clubs whose notices are extracted as facts and a link; rule 7 still keeps a
`refuse` organization's rows off every phone until its permission is recorded.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import page_notice

SECTIONS = (
    "burton",
    "mogadore",
    "massillon",
    "bowerston",
    "belle_valley",
    "stockport",
    "road_fork",
    "whipple",
    "new_straitsville",
    "old_mans_cave",
    "scioto_trail",
    "sinking_spring",
    "shawnee",
    "west_union",
    "williamsburg",
    "loveland",
    "caesar_creek",
    "troy",
    "st_marys",
    "delphos",
    "defiance",
    "pemberville",
    "norwalk",
    "medina",
    "akron",
    "bedford",
)
SECTION_CADENCE_REASON = "one of 26 Buckeye Trail section pages on one host, from a `refuse` organization whose rows cannot publish until its permission is recorded (ELT.md, 'Who may publish', rule 7); read daily, so the club's site is asked 26 times a day rather than 624 for rows no hiker can see yet"

CLAIMS = (*(f"bta_section_{part}" for part in SECTIONS),)
RESOURCES = [
    *(page_notice(f"bta_section_{part}", cadence_override="daily", cadence_reason=SECTION_CADENCE_REASON) for part in SECTIONS)
]
