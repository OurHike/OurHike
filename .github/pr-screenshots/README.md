# Pull request screenshots

One image per pull request — or a before-and-after pair where the difference is
the point — committed as evidence of what that pull request changed. A pull
request body cannot hold image bytes — GitHub's own upload
endpoint is part of the web UI rather than the REST API, and a screenshot
base64-encodes to more than the 65,536-character body limit (105,720
characters for a measured 79,290-byte PNG) — so the picture is committed here
and the body links into the commit that added it.

Take one with `cd client && node scripts/screenshot.mjs <name>`. The rule, the
byte budget, and the four things that must never appear in a screenshot are in
[`.claude/skills/pr-screenshot/SKILL.md`](../../.claude/skills/pr-screenshot/SKILL.md).

**This is the one place generated files are committed on purpose**, against
CONTRIBUTING.md's "Data does not go in commits". The exception is narrow: a
screenshot is evidence about this repository's own code, so the licence, safety
and personal-data arguments do not apply — but the bytes are still permanent, so
the count stays at one (or a pair) and re-runs reuse the file name rather than
adding a shot per push.
