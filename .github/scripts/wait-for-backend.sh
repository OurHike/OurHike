#!/usr/bin/env bash
#
# Asks a freshly deployed Fly app whether it is actually serving, and says so
# in terms of the app rather than the platform.
#
# `flyctl deploy` returning 0 means the machines were replaced and Fly is
# satisfied with them. It does not mean the FastAPI process came up: an app
# missing a required environment variable exits at import time, because
# app/config.py builds Settings() with no defaults for the Supabase fields on
# purpose. Fly restarts it, the deploy still reports success, and the first
# thing to notice would otherwise be a hiker's queued report failing to send.
#
# So this checks the body and not only the status. A 200 can come from
# something in front of the app; `{"status": "ok"}` comes from app/main.py's
# health endpoint and from nothing else.
#
# One argument: the fly config to read the app name out of, relative to the
# repository root. Shared by both legs of deploy-backend.yml rather than
# written twice, because the retry window and the body check are the parts
# worth getting right once.

set -euo pipefail

CONFIG="${1:?usage: wait-for-backend.sh <path to fly config>}"

if [ ! -f "$CONFIG" ]; then
  echo "::error::$CONFIG does not exist, so there is no app name to check."
  exit 1
fi

# The same one-line parse the workflow's summary steps use. A full toml parser
# would be more correct and would need a language runtime installed on a job
# whose only other dependency is flyctl; `app` is the first key in both files
# and its value is a Fly app name, which may hold only lowercase letters,
# digits and hyphens.
APP="$(sed -n 's/^app *= *"\(.*\)"/\1/p' "$CONFIG" | head -1)"

if [ -z "$APP" ]; then
  echo "::error::No \`app\` key in $CONFIG. That is what \`fly deploy --config\` reads to decide which app it is deploying, so this run deployed nothing recognisable."
  exit 1
fi

URL="https://$APP.fly.dev/health"
ATTEMPTS=30

echo "Waiting for $URL"

for attempt in $(seq 1 "$ATTEMPTS"); do
  # --max-time rather than letting curl hang: a machine that is still booting
  # holds the connection open, and thirty of those in series would run past the
  # job's own timeout and report as a stuck job rather than a slow app.
  body="$(curl -sS --max-time 10 "$URL" 2>/dev/null || true)"
  if echo "$body" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'; then
    echo "$APP answered on attempt $attempt."
    exit 0
  fi
  echo "Attempt $attempt: no healthy response yet."
  sleep 5
done

echo "::error::$APP did not answer $URL with {\"status\": \"ok\"} after $ATTEMPTS attempts. The deploy reported success, so the machines were replaced - check \`fly logs -a $APP\` for a process exiting at startup, which is what a missing secret looks like (backend/README.md, Auth)."
exit 1
