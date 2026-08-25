# Pull request screenshots

One image per pull request, committed as evidence of what that pull request
changed. A pull request body cannot hold image bytes — GitHub's own upload
endpoint is part of the web UI rather than the REST API, and a `data:` URI is
both stripped by the markdown sanitiser and larger than the 65,536-character
body limit — so the picture is committed here and the body links into the
commit that added it.

Take one with `cd client && node scripts/screenshot.mjs <name>`. The rule, the
byte budget, and the four things that must never appear in a screenshot are in
[`.claude/skills/pr-screenshot/SKILL.md`](../../.claude/skills/pr-screenshot/SKILL.md).

**This is the one place generated files are committed on purpose**, against
CONTRIBUTING.md's "Data does not go in commits". The exception is narrow: a
screenshot is evidence about this repository's own code, so the licence, safety
and personal-data arguments do not apply — but the bytes are still permanent, so
it is one image per pull request and re-runs reuse the file name.
