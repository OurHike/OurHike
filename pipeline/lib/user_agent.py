"""Who this pipeline says it is, in one place.

WHY THIS IS LOAD-BEARING RATHER THAN COURTESY, and the evidence is one
host's rather than a general claim. `lib/atc_scrape.py` measured ATC's host
on 2026-08-24, the same URL in the same second:

    python-requests/2.32.3   403
    curl/8.5.0               200
    (this string)            200

So against appalachiantrail.org a fetcher that sets no User-Agent gets
nothing at all. That is one host and is not evidence about the others -
`fetch_nynjtc_long_path_guide.py` records the opposite finding for NYNJTC
("does not refuse scripted agents, verified for their alerts feed on
2026-08-27"), and nothing has been measured either way for the rest. The
string is sent everywhere regardless, because an operator who wants to
throttle or contact us should be able to see who this is from one line of
their log.

It names the project and links to it rather than impersonating a browser.
ATC's block is on the default agent, not on robots.

WHY THIS MODULE EXISTS (#1295). The same literal was written out seven times
- `lib/atc_scrape.py`, `fetch_nynjtc_alerts.py`, `fetch_club_pdfs.py`,
`fetch_trail_water.py`, `fetch_nynjtc_long_path_guide.py`,
`build_shelter_capacity.py` and `build_water_distance.py` - with the
measurement above beside exactly one of them. Two consequences, and the
second is the one that bites: a reader of the other six could not tell the
string was mandatory, and `VERSION` below could no longer be moved without
finding all seven.

THE TWO FORMS ARE NOT INTERCHANGEABLE. Wikimedia's API etiquette requires a
way to reach whoever runs the client, so the photo fetchers send
`CONTACTABLE_USER_AGENT`; everything else sends `USER_AGENT`. Both are
derived from the same three parts below rather than spelled out, so a
version bump moves one line and both forms follow - which is the whole point
of the module and the thing seven copies had taken away.
"""

from __future__ import annotations

#: The three parts every form is built from. `VERSION` is the pipeline's own
#: agent version, deliberately not tied to the app's release number in
#: `client/package.json`: it identifies the fetching client to somebody
#: else's server logs, and bumping it should mean "how this client behaves
#: changed", not "the app shipped a feature".
PROJECT = "OurHike-pipeline"
VERSION = "1.0"
REPO_URL = "https://github.com/OurHike/OurHike"

#: The default, for every host that just wants to know who is calling. The
#: `+` before the URL is the long-standing convention for "this is where to
#: read about the agent" and is kept because it is what ATC's host was
#: measured against.
USER_AGENT = f"{PROJECT}/{VERSION} (+{REPO_URL})"

#: Wikimedia's form. Their API etiquette page asks for a descriptive agent
#: carrying a route to the operator, and the repository's issues are that
#: route. Note the absent `+`: this is a contact block rather than a
#: reference link, and it is the string those APIs have been answering.
CONTACTABLE_USER_AGENT = f"{PROJECT}/{VERSION} ({REPO_URL}; contact via repository issues)"
