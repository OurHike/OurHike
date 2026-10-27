# Campsite Steward's database

The `steward` schema in OurHike's Supabase project (#1906, #1910). The web app
talks to it directly through Supabase; there is no API server. That was the
maintainer's choice by poll on 2026-10-27 ("this really is meant to be open
source data"), recorded in [PLAN.md](../PLAN.md)'s decisions table.

- `migrations/0001_steward.sql` is the whole schema, in plain SQL:
  - the tables, with row-level security on and no grants, so nothing reaches
    them directly;
  - one function per action, holding the rules (the 14-day clock, the caps,
    the crew, the review). Each is `SECURITY DEFINER` with an empty
    `search_path`;
  - three `open_*` views, which are everything a signed-out reader sees. Names
    appear only on verified work;
  - the public `steward-photos` bucket and its policies: only a claim's crew
    uploads to it, only while the claim is open, and nothing is overwritten.
- `steward_db/migrate.py` applies the migrations, each once.
- `steward_db/load_sites.py` is the analysis job's daily load of the scored
  sites, which every claim and every club's weights are checked against.
- `tests/` runs the schema on plain Postgres. `tests/supabase_stand_ins.sql`
  stands in for Supabase's `auth` and `storage` schemas.

## Testing

```
scripts/local-roles.sh            # once: Supabase's roles on the local Postgres
python -m pytest -q
```

`scripts/test.sh` picks this suite up as `steward-db`, and the session-start
hook runs `local-roles.sh`. CI's Postgres logs in as a superuser, so the suite
creates the roles itself there.

**Not tested here:**

- **Token verification.** PostgREST checks the token's signature, expiry and
  audience before a function runs. The old API checked these itself, and its
  tests went with it.
- **The bucket's type and size limits.** The Storage service enforces
  `allowed_mime_types` and `file_size_limit`, not Postgres.

## Setting it up on Supabase (the maintainer's, once)

1. **Expose the schema.** Add `steward` to Settings → API → Exposed schemas.
   Until then the app's calls answer 406, and the daily open-data export
   writes nothing and says so.
2. **Apply the migrations,** as a reviewed step, never on deploy (the rule
   `backend/README.md` sets for OurHike's own). Use the session pooler on
   port 5432:

   ```
   python -m steward_db.migrate --database-url "$URL" --dry-run
   python -m steward_db.migrate --database-url "$URL"
   ```

   The runner first checks that the database looks like a Supabase project.
   It also checks that the role it runs as bypasses row-level security or
   owns `storage.objects`. The steward functions read `storage.objects` as
   their owner; a role subject to its policies would see no objects there,
   and every photo would be refused as not arrived. Supabase's `postgres`
   role is assumed to bypass row-level security. That is not checked against
   a real project here, and the runner stops if it is wrong.
3. **Give the loader a login.** The migration creates the role
   `steward_loader`, which may call `steward.load_sites()` and nothing else.
   Make a login in it:

   ```sql
   create role steward_sites_loader login password '<a new password>' in role steward_loader;
   ```

   Then set the repository secret `STEWARD_SITES_DATABASE_URL` to that
   login's session-pooler address. Until it is set, the analysis workflow's
   `load-sites` job skips with a notice, and no site can be claimed.

## What anyone can read

Through Supabase's REST API, with the project's public anon key and the
header `Accept-Profile: steward`:

| View | Holds |
|---|---|
| `open_claims` | Every claim: site, state, dates and crew size; claimer, reviewer, steps and verified hours on verified work only |
| `open_photos` | The before and after photos of verified work, by their path in `steward-photos` |
| `open_weights` | Every change to every club's ranking weights, with its changer's name as it was then |

The same three are written daily as CSV and Parquet to `data/work/` beside
`sites.json` (`apps/steward/pipeline/steward_analysis/open_data.py`).
