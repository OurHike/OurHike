# Site Remediation's database

The `remediation` schema in OurHike's Supabase project (#1906, #1910). The web app
talks to it directly through Supabase; there is no API server. That was the
maintainer's choice by poll on 2026-10-27 ("this really is meant to be open
source data"), recorded in [PLAN.md](../PLAN.md)'s decisions table.

- `migrations/0001_remediation.sql` is the whole schema, in plain SQL:
  - the tables, with row-level security on and no grants, so nothing reaches
    them directly;
  - one function per action, holding the rules: the 14-day clock, the caps,
    one person per claim, marking work done and a site's three follow-up
    visits (decided 2026-10-28: no crew, no review). Each is
    `SECURITY DEFINER` with an empty `search_path`;
  - four `open_*` views, which are everything a signed-out reader sees. Names
    appear only on done work;
  - the private `remediation-photos` bucket and its policies:
    - only the claimer uploads to it, while the claim is open, within a
      per-claim and a per-account cap, and nothing is overwritten;
    - a photo is read by its claimer, and by anyone once the work is done.

    Reading is what lets someone make a signed link, and a link outlives the
    access it was made with until it expires.
- `remediation_db/migrate.py` applies the migrations, each once.
- `remediation_db/load_sites.py` is the analysis job's daily load of the scored
  sites, which every claim and every club's weights are checked against. It
  refuses a load with under half the sites, or half the workable sites, of
  the largest load of the last 30 days. That job installs `requirements.txt`, which is
  psycopg alone and hash-pinned, and reads its login from
  `REMEDIATION_SITES_DATABASE_URL`.
- `tests/` runs the schema on plain Postgres. `tests/supabase_stand_ins.sql`
  stands in for Supabase's `auth` and `storage` schemas.

## Testing

```
scripts/local-roles.sh            # once: Supabase's roles on the local Postgres
python -m pytest -q
```

`scripts/test.sh` picks this suite up as `remediation-db`, and the session-start
hook runs `local-roles.sh`. CI's Postgres logs in as a superuser, so the suite
creates the roles itself there.

**Not tested here:**

- **Token verification.** PostgREST checks the token's signature, expiry and
  audience before a function runs. The old API checked these itself, and its
  tests went with it.
- **The bucket's type and size limits.** The Storage service enforces
  `allowed_mime_types` and `file_size_limit`, not Postgres.
- **What Storage does with the policies.** The tests insert, read and delete
  `storage.objects` rows as Storage would. Three behaviours come from
  Supabase's documentation and were not tried against a real project:
  - a signed link is checked against the select policy when it is made and
    not after;
  - a delete needs the select policy too;
  - a plain upload needs only the insert policy.

## Setting it up on Supabase (the maintainer's, once)

1. **Expose the schema.** Add `remediation` to Settings → API → Exposed schemas.
   Until then the app's calls answer 406, and the daily open-data export
   writes nothing and says so.
2. **Apply the migrations,** as a reviewed step, never on deploy (the rule
   `backend/README.md` sets for OurHike's own). Use the session pooler on
   port 5432:

   ```
   python -m remediation_db.migrate --database-url "$URL" --dry-run
   python -m remediation_db.migrate --database-url "$URL"
   ```

   The runner first checks that the database looks like a Supabase project.
   It also checks that the role it runs as bypasses row-level security or
   owns `storage.objects`. The remediation functions read `storage.objects` as
   their owner; a role subject to its policies would see no objects there,
   and every photo would be refused as not arrived. Supabase's `postgres`
   role is assumed to bypass row-level security. That is not checked against
   a real project here, and the runner stops if it is wrong.
3. **Give the loader a login.** The migration creates the role
   `remediation_loader`, which may call `remediation.load_sites()` and nothing else.
   Make a login in it:

   ```sql
   create role remediation_sites_loader login password '<a new password>' in role remediation_loader;
   ```

   Then set the repository secret `REMEDIATION_SITES_DATABASE_URL` to that
   login's session-pooler address. Until it is set, the analysis workflow's
   `load-sites` job skips with a notice, and no site can be claimed.

## What anyone can read

Through Supabase's REST API, with the project's public anon key and the
header `Accept-Profile: remediation`:

| View | Holds |
|---|---|
| `open_claims` | Every claim and follow-up visit: site, kind, state and dates; the claimer's name, steps and hours on done work only |
| `open_photos` | The before and after photos of done work, by their path in `remediation-photos`: `<claim id>/<photo id>.jpg` |
| `open_follow_ups` | Every restored site's three follow-up visits: when each opens and closes, and how it stands |
| `open_weights` | Every change to every club's ranking weights, with its changer's name as it was then |

The bucket is private, so a photo is fetched through a link Storage signs:
`POST /storage/v1/object/sign/remediation-photos` with the same key and the
photo's path. The policy signs any done claim's photo for anyone.

The same four are written daily as CSV and Parquet to `data/work/` beside
`sites.json` (`apps/remediation/pipeline/remediation_analysis/open_data.py`). The
photos file carries a link to each photo, signed for eight days.

**Anyone who may read a photo may sign a link to it for as long as they
like.** Storage takes the lifetime from whoever asks, so a done photo can be
linked to for years. With no review, one account can get any 40 JPEG-typed
uploads published by claiming a site, uploading them and marking it done
(PLAN.md §10).
