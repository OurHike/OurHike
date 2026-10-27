"""Every size and count the API enforces, in one place.

`@unvalidated`, all of them: picked to sit well above what a club volunteer
is expected to do and far below what would let one account fill the
database. Nobody has measured real use; the numbers to compare against,
once there is some, are the largest list and the busiest weights history.
"""

#: Each of the need score's five weights, in the analysis job's order
#: (apps/steward/pipeline/steward_analysis/rules.py, WEIGHT_NAMES). A test
#: holds the two equal.
WEIGHT_NAMES = ("deficit", "water", "trail", "cluster", "restricted")

#: A weight is a whole number of points from 0 to this. The need score is
#: clamped to 100, so a larger weight could only ever saturate it.
WEIGHT_MAX = 100

#: The defaults, the job's rules.DEFAULT_WEIGHTS: what a club's ranking is
#: until somebody changes it. Also held equal to the job's by a test.
DEFAULT_WEIGHTS = {"deficit": 60, "water": 12, "trail": 6, "cluster": 8, "restricted": 10}

DISPLAY_NAME_MAX = 40
LIST_NAME_MAX = 80
NOTE_MAX = 200
#: ATC's RIMS_ID: all 3,442 are 36-character GUIDs (measured 2026-10-27); 64
#: and the pattern below leave room for a format change without accepting markup.
RIMS_ID_MAX = 64
RIMS_ID_PATTERN = r"^[A-Za-z0-9-]{1,64}$"
#: The longest of the 29 club names in the CSI layer is 57 characters (2026-10-27).
CLUB_MAX = 120

LISTS_PER_USER = 50
ITEMS_PER_LIST = 500
#: Weights changes one account may make across all clubs in 24 hours. Open
#: editing is decided (PLAN.md §10, "Open weights"); this caps how fast one
#: account can bury a club's history in noise.
WEIGHT_CHANGES_PER_DAY = 30

#: Any request body, in bytes. The largest legitimate one is a list rename.
MAX_BODY_BYTES = 16 * 1024

# --- Claims (phase 3, #1910) ------------------------------------------------------

#: How long a claim lasts before it is released: the original request's two
#: weeks (PLAN.md §6, `@unvalidated` there: how many claims are released
#: unfinished, by season, would settle it).
CLAIM_DAYS = 14
#: Days an account that rejected a claim must wait before claiming that site.
#: `@unvalidated`: long enough that rejecting cannot be a quick way to take a
#: site; what would settle it is how often rejects happen at all.
REJECTER_WAIT_DAYS = 30
#: How long a crew gets after a reviewer sends a submission back. Picked:
#: PLAN.md stops the clock at Submitted and says nothing about restarting it.
SEND_BACK_DAYS = 7
#: Sites one account may hold at once, counting claims it has submitted and
#: that wait for review, since those hold their sites too (the review's
#: finding 2). High enough to claim a cluster (most are 2-3 sites; the largest
#: is 28, 2026-10-26).
LIVE_CLAIMS_PER_USER = 10
#: Sites in one "claim all" request.
SITES_PER_CLAIM_REQUEST = 10
CREW_MAX = 12

#: The fixed photo points every submission photographs before and after (PLAN.md §5).
PHOTO_POINTS = (1, 2)
#: One photo as it arrives, after the phone has re-encoded it (2048 px on the
#: long side at JPEG quality 0.85 is typically under 1 MB).
PHOTO_MAX_BYTES = 3 * 1024 * 1024
#: The longest side, in pixels, of a photo the API accepts. Reasoned: the app
#: redraws every photo to at most this on its long side before sending
#: (web/src/photo.ts), so nothing it sends is larger, and a camera original is
#: refused unread. Each side, not width x height: the re-check's N1 measured a
#: 15 KB PNG of 1 x 4,194,304 px, inside a 2048 x 2048 pixel budget, costing
#: 140 MB to decode; 60 MP had cost 687 MB before any cap at all.
PHOTO_LONG_SIDE = 2048
#: Seconds a photo's upload may go without a byte arriving, and in all. Idle
#: rather than only a total, so a weak trailhead signal that keeps trickling
#: still gets its photo through (the re-check's N5), while a stalled one is
#: cut off. `@unvalidated`, both: nobody has timed an upload on the trail.
PHOTO_IDLE_SECONDS = 20
PHOTO_READ_SECONDS = 300
PHOTOS_PER_CLAIM = 40
#: The phone's id for a photo (web/src/offline.ts newPhotoId): letters,
#: digits, - and _, so it can sit in a query string unescaped.
CLIENT_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
#: What a queued photo's `replaces` may say: a photo id, or that its slot was empty.
REPLACES_PATTERN = r"^(nothing|[0-9a-fA-F-]{36})$"
#: Photos one account may have arriving at once (routes/claims._sending).
#: Reasoned: the web app sends one at a time (web/src/offline.ts runs one send
#: at a time, and the claim screen waits for each upload), so four leaves room
#: for two phones on one account and refuses only a script.
PHOTO_UPLOADS_AT_ONCE = 4
#: Photos decoded at once, process-wide (main.create_app's limiter). Each holds
#: its decoded pixels while it runs (about 13 MB at the size cap); the rest
#: wait without holding a worker thread. `@unvalidated`: two keeps a second
#: photo from waiting behind the first on a small instance; nothing has
#: measured the instance.
REENCODE_AT_ONCE = 2
#: Hours one person logs on one claim, across all their visits to it.
HOURS_MAX = 72

NOTES_MAX = 1000
REVIEW_NOTE_MAX = 500
STEP_MAX = 120
STEPS_MAX = 20

#: How long /health reuses its last database check (main.CachedCheck).
#: `@unvalidated`: short enough that a database that goes away shows within a
#: few seconds, long enough that a flood of probes costs one query per period.
#: Render's own probe interval and failure count, which would settle it, have
#: not been read from its documentation here.
HEALTH_CHECK_SECONDS = 5
