"""Blue Mountain Eagle Climbing Club: warnings, 2 notice sources read here (decision 53 phase B,
2026-10-03).

- `bmecc_fluorescent_orange`: BMECC: Fluorescent Orange, one notice for the page (PageNotice).
  Pennsylvania Game Commission's fluorescent-orange rule for State Game Lands (Nov 15 - Dec 15), as
  the club restates it. The authority is the PGC. The page states no date of its own.

- `bmecc_appalachian_trail`: BMECC: Appalachian Trail hiker information, one notice for the page
  (PageNotice). The club's A.T. page, whose parking notes carry 'Hamburg Reservoir parking lot has
  NO overnight parking'. The page states no date of its own.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Blue Mountain Eagle Climbing Club: warnings, published, and not landed (coverage audit 2026-10-01,
batch c2_at_clubs_mid).

These are evergreen pages, not dated notices. The hunting rule is a fixed-window seasonal warning,
and the authority behind it is the PA Game Commission, so `_shared` should take it from PGC itself
(Reasoned).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/appalachian-trail/fluorescent-orange` (page): "unlawful to
be on state game lands from November 15 through December 15 without wearing a minimum of 250 square
inches of fluorescent orange". The page says the rule "applies to Everyone", and the A.T. crosses PA
State Game Lands "many times". `/appalachian-trail/bear-canisters` (page): free canister loans.
`/appalachian-trail` (page): parking vandalism; Hamburg Reservoir "NO overnight parking… ticketed
and towed"

Its `where`: https://bmecc.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import page_notice

CLAIMS = ("bmecc_fluorescent_orange", "bmecc_appalachian_trail")
RESOURCES = [page_notice("bmecc_fluorescent_orange"), page_notice("bmecc_appalachian_trail")]
