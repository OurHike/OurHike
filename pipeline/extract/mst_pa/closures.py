"""Mid State Trail Association (PA): closures, 23 notice sources read here (decision 53 phase B,
2026-10-03).

- `msta_<part>`, 23 sources, the Mid State Trail's 23 section articles, in the order its
  section-updates list gives them: one notice for the page (PageNotice) each. One of the 23 section
  articles https://hike-mst.org/index.php/the-trail/section-updates lists, each with its own 'Last
  Updated on' date and an 'Alerts:' list. The Joomla RSS and Atom feeds carry each article's 2012
  creation date and the request time, so they cannot see an edit and are not read. Read daily: one
  of 23 Mid State Trail section articles on one host whose only change signal is each article's own
  'Last Updated on' line; 23 reads a day rather than 552, as the decision 53 inventory reasoned
  (batch 2), at the cost of a day's lag on a new alert (@unvalidated until phase F measures the
  hourly lane's budget).

Not read: the Joomla feeds of the list page
(https://hike-mst.org/index.php/the-trail/section-updates?format=feed&type=rss and its Atom twin):
their dates are each article's 2012 creation date and the request time, so they cannot see an edit;
and the region update pages of 2009 to 2014. The footer reads 'Copyright 2012 - Mid State Trail
Association. All rights reserved.', a copyright notice that restricts copying and not reading, so
these rows rest on decision 55.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import page_notice

SECTIONS = (
    "section_1",
    "section_2",
    "section_3",
    "section_4",
    "section_5",
    "section_6",
    "section_7",
    "section_8",
    "section_9",
    "section_10",
    "section_11",
    "section_12",
    "section_13",
    "section_14",
    "section_15",
    "section_16",
    "section_17",
    "section_18",
    "section_19",
    "section_20",
    "section_a",
    "section_b",
    "section_c",
)
SECTION_CADENCE_REASON = "one of 23 Mid State Trail section articles on one host whose only change signal is each article's own 'Last Updated on' line; 23 reads a day rather than 552, as the decision 53 inventory reasoned (batch 2), at the cost of a day's lag on a new alert (@unvalidated until phase F measures the hourly lane's budget)"

CLAIMS = (*(f"msta_{part}" for part in SECTIONS),)
RESOURCES = [*(page_notice(f"msta_{part}", cadence_override="daily", cadence_reason=SECTION_CADENCE_REASON) for part in SECTIONS)]
