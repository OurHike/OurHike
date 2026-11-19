-- Site Remediation's data, in OurHike's Supabase project (#1906, #1910; PLAN.md,
-- decided 2026-10-27: "no API server: the app talks to Supabase directly").
--
-- How it is put together:
--   - Every table is in the `remediation` schema, with row-level security on and no
--     grant to anon or authenticated: nothing reaches a table directly.
--   - Every change goes through a function below. Each is SECURITY DEFINER with
--     an empty search_path, checks who is calling, and carries the rule the old
--     Python API carried (apps/remediation/api, retired by this change). Their
--     messages are the ones the web app shows.
--   - Errors carry an HTTP status as SQLSTATE PTnnn, which PostgREST turns into
--     that status: PT401 sign in, PT403 not yours, PT404 no such thing,
--     PT409 not in this state or over a cap, PT412 the slot changed,
--     PT422 not acceptable, PT429 too many today.
--   - What is open, anyone may read: the open_* views, which carry names only
--     on done work (decided 2026-10-27, by poll: "the public sees that a site
--     is claimed and when it is due, not who will be out there"; done is
--     public at once since review went, 2026-10-28).
--   - Photos live in the private Storage bucket `remediation-photos`, under
--     `<claim id>/<the phone's id for the photo>.jpg`.

create schema if not exists remediation;
revoke all on schema remediation from public;
grant usage on schema remediation to anon, authenticated;
-- Postgres lets PUBLIC execute every new function. Nothing here may be
-- executed unless it is granted by name below.
alter default privileges in schema remediation revoke execute on functions from public;

-- The analysis job loads the latest list of sites through load_sites() and
-- nothing else (apps/remediation/db/README.md: give it a login of its own).
do $$
begin
  if not exists (select from pg_roles where rolname = 'remediation_loader') then
    create role remediation_loader nologin;
  end if;
end
$$;
grant usage on schema remediation to remediation_loader;


-- ---------------------------------------------------------------------------
-- Limits. `@unvalidated`, all of them, carried over from the old API's
-- limits.py: picked to sit well above what a club volunteer is expected to do
-- and far below what would let one account fill the database. Nobody has
-- measured real use; the numbers to compare against, once there is some, are
-- the largest list, the busiest weights history and the most photos a claim.
-- ---------------------------------------------------------------------------

create function remediation.claim_days() returns int language sql immutable as 'select 14';
-- Sites one account holds at once. High enough for a cluster: most are 2-3
-- sites (2026-10-26).
create function remediation.live_claims_per_user() returns int language sql immutable as 'select 10';
create function remediation.sites_per_claim_request() returns int language sql immutable as 'select 10';
create function remediation.photos_per_claim() returns int language sql immutable as 'select 40';
-- Objects one claim may hold in the bucket: photos replaced or removed stay
-- until the claimer's phone deletes them, so twice the photo cap.
create function remediation.objects_per_claim() returns int language sql immutable as 'select 80';
-- Photos one account may have uploaded and not yet put on a claim, and may
-- upload in a day. Together they are what keeps the bucket from being anyone's
-- file host (the sixth review pass, finding 1): a photo is uploaded and put on
-- its claim within seconds, and a busy day is a few photos per site.
create function remediation.pending_uploads_per_user() returns int language sql immutable as 'select 20';
create function remediation.uploads_per_user_per_day() returns int language sql immutable as 'select 150';
create function remediation.hours_max() returns int language sql immutable as 'select 72';
create function remediation.lists_per_user() returns int language sql immutable as 'select 50';
create function remediation.items_per_list() returns int language sql immutable as 'select 500';
create function remediation.weight_changes_per_day() returns int language sql immutable as 'select 30';
create function remediation.weights_history_limit() returns int language sql immutable as 'select 50';
-- The need score's defaults: apps/remediation/pipeline/remediation_analysis/rules.py
-- DEFAULT_WEIGHTS, which a test holds equal to this.
create function remediation.default_weights() returns jsonb language sql immutable as
  $$ select '{"deficit": 60, "water": 12, "trail": 6, "cluster": 8, "restricted": 10}'::jsonb $$;

-- ATC's RIMS_ID: all 3,442 are 36-character GUIDs (2026-10-27); this leaves
-- room for a format change without accepting markup.
create function remediation.rims_id_pattern() returns text language sql immutable as $$ select '^[A-Za-z0-9-]{1,64}$' $$;
-- The phone's id for a photo (web/src/offline.ts newPhotoId).
create function remediation.client_id_pattern() returns text language sql immutable as $$ select '^[A-Za-z0-9_-]{1,64}$' $$;
-- <claim id>/<the phone's id for the photo>.jpg. A claim is one person's
-- (decided 2026-10-28), so the claim names the uploader, and the name names
-- nobody.
create function remediation.photo_object_pattern() returns text language sql immutable as
  $$ select '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/[A-Za-z0-9_-]{1,64}\.jpg$' $$;

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

-- The latest analysis's sites: which may be claimed, and which clubs exist.
-- Written only by load_sites().
create table remediation.site (
  rims_id text primary key check (rims_id ~ '^[A-Za-z0-9-]{1,64}$'),
  club text,
  workable boolean not null,
  loaded_at timestamptz not null default now()
);
create index site_club on remediation.site (club);

create table remediation.profile (
  user_id uuid primary key references auth.users (id) on delete cascade,
  display_name text check (char_length(display_name) between 1 and 40),
  -- Set by delete_my_data(). The row stays, so the history that points at it
  -- still does (the review's finding 3); signing in again clears it.
  deleted_at timestamptz,
  created_at timestamptz not null default now()
);

create table remediation.site_list (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references remediation.profile (user_id) on delete cascade,
  name text not null check (char_length(name) between 1 and 80),
  share_token_sha256 text unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index site_list_owner on remediation.site_list (owner_id);

create table remediation.site_list_item (
  list_id uuid not null references remediation.site_list (id) on delete cascade,
  rims_id text not null check (rims_id ~ '^[A-Za-z0-9-]{1,64}$'),
  seq bigint generated always as identity,
  primary key (list_id, rims_id)
);

create table remediation.club_weights (
  id bigint generated always as identity primary key,
  club text not null check (char_length(club) between 1 and 120),
  deficit int not null check (deficit between 0 and 100),
  water int not null check (water between 0 and 100),
  trail int not null check (trail between 0 and 100),
  cluster int not null check (cluster between 0 and 100),
  restricted int not null check (restricted between 0 and 100),
  note text check (char_length(note) between 1 and 200),
  restored_from bigint references remediation.club_weights (id),
  changed_by uuid references remediation.profile (user_id) on delete set null,
  -- The name its changer used at the time, so a rename cannot rewrite the
  -- history (the review's finding 10). Cleared by delete_my_data().
  changed_by_name text,
  changed_at timestamptz not null default now()
);
create index club_weights_club_changed on remediation.club_weights (club, changed_at desc, id desc);
create index club_weights_changed_by on remediation.club_weights (changed_by, changed_at);

-- One person's claim on one site (PLAN.md §6, decided 2026-10-28: one person,
-- no review). A follow-up visit is a claim too, with follow_up_id set.
create table remediation.claim (
  id uuid primary key default gen_random_uuid(),
  rims_id text not null check (rims_id ~ '^[A-Za-z0-9-]{1,64}$'),
  claimer_id uuid references remediation.profile (user_id) on delete set null,
  state text not null check (state in ('claimed', 'in_progress', 'done', 'released')),
  claimed_at timestamptz not null default now(),
  due_at timestamptz not null,
  started_at timestamptz,
  done_at timestamptz,
  released_at timestamptz,
  steps_done text[] not null default '{}',
  notes text,
  -- The claimer's hours on the site, in tenths. Null until logged, and after
  -- the claimer deletes their data.
  hours_tenths int check (hours_tenths > 0 and hours_tenths <= 720)
);
-- One claim holds a site at a time; it is what refuses the second of two
-- claims made at the same moment.
create unique index claim_one_holder_per_site on remediation.claim (rims_id)
  where state in ('claimed', 'in_progress');
create index claim_state_due on remediation.claim (state, due_at);
create index claim_claimer on remediation.claim (claimer_id);

-- A restored site's follow-up visits (PLAN.md §6; decided 2026-10-28): three,
-- made when the work is marked done. Visit 1 opens the day after the first
-- Labor Day after that, visits 2 and 3 the day after each of the next two.
-- Each is open until the next one opens, the third for a year, and anyone
-- may take one as a claim of its own.
create table remediation.follow_up (
  id uuid primary key default gen_random_uuid(),
  rims_id text not null,
  done_claim_id uuid not null references remediation.claim (id) on delete cascade,
  visit int not null check (visit between 1 and 3),
  opens_on date not null,
  closes_on date not null,
  unique (done_claim_id, visit),
  check (closes_on > opens_on)
);
create index follow_up_site on remediation.follow_up (rims_id, opens_on);

alter table remediation.claim add column follow_up_id uuid references remediation.follow_up (id) on delete cascade;
-- A follow-up is taken by one claim at a time and done once.
create unique index claim_one_per_follow_up on remediation.claim (follow_up_id)
  where follow_up_id is not null and state in ('claimed', 'in_progress', 'done');

create table remediation.photo (
  id uuid primary key default gen_random_uuid(),
  claim_id uuid not null references remediation.claim (id) on delete cascade,
  phase text not null check (phase in ('before', 'after', 'extra')),
  point int check (point in (1, 2)),
  -- Its name in the remediation-photos bucket.
  object_name text not null,
  created_at timestamptz not null default now(),
  check ((phase = 'extra') = (point is null))
);
-- One before and one after per photo point; a new one replaces it.
create unique index photo_one_per_slot on remediation.photo (claim_id, phase, point) where point is not null;
-- An object is one photo's: its name carries the claim and the phone's id,
-- and a phone's id is taken once per claim (photo_receipt).
create unique index photo_object on remediation.photo (object_name);

-- Every photo a claim has received, by the phone's id for it, kept after the
-- photo is replaced or removed, so a phone sending it again after a lost
-- answer stores nothing new and brings nothing back (the third pass's P2,
-- the fourth pass's C).
create table remediation.photo_receipt (
  claim_id uuid not null references remediation.claim (id) on delete cascade,
  client_id text not null,
  received_at timestamptz not null default now(),
  primary key (claim_id, client_id)
);

-- Every load's size for 90 days, so a load is held against the month's
-- largest and not only the last: halving one load at a time could otherwise
-- empty the list in a few days (the sixth pass, finding 4).
create table remediation.site_load (
  id bigint generated always as identity primary key,
  loaded_at timestamptz not null default now(),
  sites int not null,
  workable int not null
);

alter table remediation.site enable row level security;
alter table remediation.site_load enable row level security;
alter table remediation.profile enable row level security;
alter table remediation.site_list enable row level security;
alter table remediation.site_list_item enable row level security;
alter table remediation.club_weights enable row level security;
alter table remediation.claim enable row level security;
alter table remediation.follow_up enable row level security;
alter table remediation.photo enable row level security;
alter table remediation.photo_receipt enable row level security;


-- ---------------------------------------------------------------------------
-- Helpers. Not granted to anyone: only the functions below call them.
-- ---------------------------------------------------------------------------

create function remediation._refuse(code text, message text) returns void
language plpgsql as $$
begin
  raise exception using errcode = code, message = message;
end
$$;

-- The signed-in caller, made a profile on first use. Refuses Supabase's
-- anonymous sign-ins, which anyone can mint without an address.
create function remediation._caller() returns uuid
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := auth.uid();
begin
  if uid is null or coalesce((auth.jwt() ->> 'is_anonymous')::boolean, false) then
    perform remediation._refuse('PT401', 'Sign in first.');
  end if;
  insert into remediation.profile (user_id) values (uid) on conflict (user_id) do nothing;
  -- Back after deleting their data: an empty account, which is what the
  -- delete left (the review's re-check, N7).
  update remediation.profile set deleted_at = null where user_id = uid and deleted_at is not null;
  return uid;
end
$$;

-- Holds the caller's profile row until the transaction ends, so a cap
-- counted next still holds when the insert lands.
create function remediation._lock(uid uuid) returns void
language sql security definer set search_path = '' as $$
  select null from remediation.profile where user_id = uid for update;
$$;

-- A person's text: trimmed, bounded, and free of control characters and the
-- invisible format characters a name can use to pass for another (bidi
-- overrides, zero-width joiners, tags, private use; the review's finding 10).
-- The old API refused Unicode categories Cc, Cf, Co, Cs and Cn by name;
-- Postgres regular expressions have no category classes, so
-- _hidden_characters() is every Cc, Cf and Co range in Unicode 15.1 written
-- out, and a test holds it to Python's unicodedata. Cs cannot occur in
-- Postgres text; unassigned code points (Cn) are not refused.
create function remediation._text(label text, value text, max_length int, multiline boolean default false) returns text
language plpgsql immutable as $$
declare
  v text := btrim(value, E' \t\r\n');
  checked text;
begin
  if value is null then
    return null;
  end if;
  if v = '' then
    perform remediation._refuse('PT422', label || ' must not be empty');
  end if;
  if char_length(v) > max_length then
    perform remediation._refuse('PT422', label || ' must be at most ' || max_length || ' characters');
  end if;
  checked := case when multiline then regexp_replace(v, E'\r?\n', ' ', 'g') else v end;
  if checked ~ remediation._hidden_characters() then
    perform remediation._refuse('PT422', label || ' must not contain control or invisible formatting characters');
  end if;
  -- Spaces of every width and variation selectors alone draw nothing.
  if regexp_replace(checked, remediation._blank_characters(), '', 'g') = '' then
    perform remediation._refuse('PT422', label || ' must not be empty');
  end if;
  return v;
end
$$;

-- What draws nothing but is allowed beside something that does: every space
-- separator (Zs) and the variation selectors.
create function remediation._blank_characters() returns text language sql immutable as $re$ select
  '[\x20\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000\u180b-\u180d\u180f\ufe00-\ufe0f\U000e0100-\U000e01ef]'
$re$;

-- Every code point Unicode calls a control (Cc), format (Cf) or private-use
-- (Co) character, and every Default_Ignorable_Code_Point (Unicode 15.1's
-- DerivedCoreProperties.txt) but the variation selectors, which give emoji
-- their colour (U+2764 U+FE0F is a red heart) and Mongolian its letter
-- forms, plus U+2800, the braille blank. Fillers like U+3164 draw nothing, so
-- a name of them reads as no name (the re-check). In ASCII escapes, so the
-- file shows what it refuses. Adjacent literals on separate lines are one
-- string in SQL.
create function remediation._hidden_characters() returns text language sql immutable as $re$ select
  '[\x01-\x1f\x7f-\x9f\u00ad\u034f\u0600-\u0605\u061c\u06dd\u070f\u0890-\u0891\u08e2'
  '\u115f-\u1160\u17b4-\u17b5\u180e\u200b-\u200f\u202a-\u202e\u2060-\u206f\u2800\u3164'
  '\ue000-\uf8ff\ufeff\uffa0\ufff0-\ufffb\U000110bd\U000110cd\U00013430-\U0001343f'
  '\U0001bca0-\U0001bca3\U0001d173-\U0001d17a\U000e0000-\U000e00ff\U000e01f0-\U000e0fff'
  '\U000f0000-\U000ffffd\U00100000-\U0010fffd]'
$re$;

create function remediation._sha256(token text) returns text
language sql immutable as $$ select encode(sha256(convert_to(token, 'UTF8')), 'hex') $$;

-- 64 hex characters, from two random UUIDs: 244 random bits.
create function remediation._token() returns text
language sql volatile as $$
  select replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', '')
$$;

-- Every working claim whose clock has run out goes back to Open. Not a
-- scheduled job: everything that reads or changes claims calls this first,
-- and the open views work the same state out for themselves.
create function remediation._release_overdue() returns void
language sql security definer set search_path = '' as $$
  update remediation.claim
     set state = 'released', released_at = due_at
   where state in ('claimed', 'in_progress') and due_at < now();
$$;

create function remediation._working(state text) returns boolean
language sql immutable as $$ select state in ('claimed', 'in_progress') $$;

-- The claim, locked for the rest of the transaction, or 404.
create function remediation._claim_for_update(claim_id uuid) returns remediation.claim
language plpgsql security definer set search_path = '' as $$
declare
  c remediation.claim;
begin
  select * into c from remediation.claim where id = claim_id for update;
  if not found then
    perform remediation._refuse('PT404', 'No such claim');
  end if;
  return c;
end
$$;

-- The claim, locked, if the caller made it and it is in one of `states`.
create function remediation._own_claim(claim_id uuid, uid uuid, states text[] default array['claimed', 'in_progress'])
returns remediation.claim
language plpgsql security definer set search_path = '' as $$
declare
  c remediation.claim := remediation._claim_for_update(claim_id);
begin
  if c.claimer_id is distinct from uid then
    perform remediation._refuse('PT403', 'Only the person who claimed this site can do that');
  end if;
  if not (c.state = any (states)) then
    perform remediation._refuse('PT409', 'This claim is ' || replace(c.state, '_', ' ') || ', so that cannot be done now');
  end if;
  return c;
end
$$;

create function remediation._display_name(uid uuid) returns text
language sql stable security definer set search_path = '' as $$
  select display_name from remediation.profile where user_id = uid
$$;

-- What anyone signed in may know of a claim. The claimer's name shows to the
-- claimer, and to everyone once the work is done; before that, nobody else
-- learns who will be out at the site (decided 2026-10-27, and kept when
-- review went on 2026-10-28: done is public at once).
create function remediation._claim_summary(c remediation.claim, uid uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'id', c.id,
    'rims_id', c.rims_id,
    'kind', case when c.follow_up_id is null then 'restore' else 'follow_up' end,
    'visit', (select f.visit from remediation.follow_up f where f.id = c.follow_up_id),
    'state', c.state,
    'claimed_at', c.claimed_at,
    'due_at', c.due_at,
    'done_at', c.done_at,
    'claimer', case when c.state = 'done' or c.claimer_id = uid then remediation._display_name(c.claimer_id) end,
    'yours', uid is not null and c.claimer_id is not distinct from uid
  )
$$;

-- A claim's photos, oldest first, as their paths in the bucket.
create function remediation._photos(claim_id uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object(
           'id', ph.id, 'phase', ph.phase, 'point', ph.point,
           'path', ph.object_name, 'created_at', ph.created_at
         ) order by ph.created_at), '[]'::jsonb)
    from remediation.photo ph where ph.claim_id = _photos.claim_id
$$;

-- What a caller sees of one claim. The claimer sees all of it, and so does
-- everyone once it is done. Anyone else sees what the open views show, with
-- `full` false, so a screen cannot read the empty lists as a claim with no
-- photos and no report (the sixth pass, finding 3). A follow-up also carries
-- the restoration's after photos, to line the new ones up with: that work is
-- done, so they are public.
create function remediation._claim_detail(claim_id uuid, uid uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare
  c remediation.claim;
  reference jsonb;
begin
  select * into c from remediation.claim where id = claim_id;
  select coalesce(jsonb_agg(p.photo) filter (where p.photo ->> 'phase' = 'after'), '[]'::jsonb) into reference
    from remediation.follow_up f
    cross join lateral jsonb_array_elements(remediation._photos(f.done_claim_id)) as p(photo)
   where f.id = c.follow_up_id;
  -- Fails closed: anything unknown here is the outside view.
  if not coalesce(c.state = 'done' or (uid is not null and c.claimer_id = uid), false) then
    return remediation._claim_summary(c, uid) || jsonb_build_object(
      'full', false,
      'started_at', null,
      'released_at', c.released_at,
      'steps_done', '[]'::jsonb,
      'notes', null,
      'hours', null,
      'photos', '[]'::jsonb,
      'reference', coalesce(reference, '[]'::jsonb)
    );
  end if;
  return remediation._claim_summary(c, uid) || jsonb_build_object(
    'full', true,
    'started_at', c.started_at,
    'released_at', c.released_at,
    'steps_done', to_jsonb(c.steps_done),
    'notes', c.notes,
    'hours', c.hours_tenths / 10.0,
    'photos', remediation._photos(c.id),
    'reference', coalesce(reference, '[]'::jsonb)
  );
end
$$;


-- ---------------------------------------------------------------------------
-- You
-- ---------------------------------------------------------------------------

create function remediation.me() returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
begin
  return jsonb_build_object('display_name', remediation._display_name(uid));
end
$$;

-- Null clears it.
create function remediation.set_display_name(p_name text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
begin
  update remediation.profile set display_name = remediation._text('Your name', p_name, 40) where user_id = uid;
  return remediation.me();
end
$$;

-- Deletes what is the caller's own: their name (here and on every history
-- entry it was copied to), their lists and their hours. Claims they were
-- working on go back to Open. What stays, without a name: their done work and
-- weights changes, which are the sites' history and the clubs'. Signing in
-- again starts an empty account. The Supabase account is OurHike's, and is
-- not touched.
create function remediation.delete_my_data() returns void
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
begin
  perform remediation._lock(uid);
  update remediation.claim
     set state = 'released', released_at = now()
   where claimer_id = uid and state in ('claimed', 'in_progress');
  update remediation.claim set hours_tenths = null where claimer_id = uid;
  update remediation.club_weights set changed_by_name = null where changed_by = uid;
  delete from remediation.site_list where owner_id = uid;
  update remediation.profile set display_name = null, deleted_at = now() where user_id = uid;
end
$$;

-- ---------------------------------------------------------------------------
-- Lists and share links. A list is its owner's alone: anyone else asking for
-- it by id gets 404, not 403, so ids cannot be probed. Sharing is a random
-- token the owner hands out; opening one needs sign-in (PLAN.md §8).
-- ---------------------------------------------------------------------------

create function remediation._list_summary(l remediation.site_list) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'id', l.id, 'name', l.name,
    'item_count', (select count(*) from remediation.site_list_item i where i.list_id = l.id),
    'shared', l.share_token_sha256 is not null,
    'created_at', l.created_at, 'updated_at', l.updated_at
  )
$$;

create function remediation._list_detail(list_id uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select remediation._list_summary(l) || jsonb_build_object('rims_ids', coalesce((
           select jsonb_agg(i.rims_id order by i.seq) from remediation.site_list_item i where i.list_id = l.id
         ), '[]'::jsonb))
    from remediation.site_list l where l.id = list_id
$$;

create function remediation._own_list(list_id uuid, uid uuid) returns remediation.site_list
language plpgsql security definer set search_path = '' as $$
declare
  l remediation.site_list;
begin
  select * into l from remediation.site_list where id = list_id and owner_id = uid for update;
  if not found then
    perform remediation._refuse('PT404', 'No such list');
  end if;
  return l;
end
$$;

create function remediation._rims_id(value text) returns text
language plpgsql immutable as $$
begin
  if value is null or value !~ remediation.rims_id_pattern() then
    perform remediation._refuse('PT422', 'That is not a site id');
  end if;
  return value;
end
$$;

create function remediation.my_lists() returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
begin
  return coalesce((
    select jsonb_agg(remediation._list_summary(l) order by l.updated_at desc)
      from remediation.site_list l where l.owner_id = uid
  ), '[]'::jsonb);
end
$$;

create function remediation.read_list(p_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
begin
  perform remediation._own_list(p_id, uid);
  return remediation._list_detail(p_id);
end
$$;

create function remediation.create_list(p_name text, p_rims_ids text[] default '{}') returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
  new_id uuid;
  rims text;
begin
  perform remediation._lock(uid);
  if (select count(*) from remediation.site_list where owner_id = uid) >= remediation.lists_per_user() then
    perform remediation._refuse('PT409', 'You already have ' || remediation.lists_per_user() || ' lists, the most one account can keep');
  end if;
  if coalesce(cardinality(p_rims_ids), 0) > remediation.items_per_list() then
    perform remediation._refuse('PT422', 'A list holds at most ' || remediation.items_per_list() || ' sites');
  end if;
  insert into remediation.site_list (owner_id, name) values (uid, remediation._text('The list''s name', p_name, 80))
  returning id into new_id;
  foreach rims in array coalesce(p_rims_ids, '{}') loop
    insert into remediation.site_list_item (list_id, rims_id) values (new_id, remediation._rims_id(rims))
    on conflict do nothing;
  end loop;
  return remediation._list_detail(new_id);
end
$$;

create function remediation.rename_list(p_id uuid, p_name text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
begin
  perform remediation._own_list(p_id, uid);
  update remediation.site_list set name = remediation._text('The list''s name', p_name, 80), updated_at = now() where id = p_id;
  return remediation._list_detail(p_id);
end
$$;

create function remediation.delete_list(p_id uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
begin
  perform remediation._own_list(p_id, uid);
  delete from remediation.site_list where id = p_id;
end
$$;

-- Saving a site twice keeps one entry.
create function remediation.add_to_list(p_id uuid, p_rims_id text) returns void
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
  rims text := remediation._rims_id(p_rims_id);
begin
  perform remediation._own_list(p_id, uid);
  if exists (select from remediation.site_list_item where list_id = p_id and rims_id = rims) then
    return;
  end if;
  if (select count(*) from remediation.site_list_item where list_id = p_id) >= remediation.items_per_list() then
    perform remediation._refuse('PT409', 'A list holds at most ' || remediation.items_per_list() || ' sites');
  end if;
  insert into remediation.site_list_item (list_id, rims_id) values (p_id, rims) on conflict do nothing;
  update remediation.site_list set updated_at = now() where id = p_id;
end
$$;

create function remediation.remove_from_list(p_id uuid, p_rims_id text) returns void
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
begin
  perform remediation._own_list(p_id, uid);
  delete from remediation.site_list_item where list_id = p_id and rims_id = p_rims_id;
  update remediation.site_list set updated_at = now() where id = p_id;
end
$$;

-- A new token, replacing any earlier one: sharing again is how a leaked link
-- is stopped. Only its hash is kept.
create function remediation.share_list(p_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
  token text := remediation._token();
begin
  perform remediation._own_list(p_id, uid);
  update remediation.site_list set share_token_sha256 = remediation._sha256(token) where id = p_id;
  return jsonb_build_object('token', token);
end
$$;

create function remediation.unshare_list(p_id uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
begin
  perform remediation._own_list(p_id, uid);
  update remediation.site_list set share_token_sha256 = null where id = p_id;
end
$$;

create function remediation.open_shared_list(p_token text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  l remediation.site_list;
begin
  perform remediation._caller();
  if p_token is null or char_length(p_token) not between 16 and 128 then
    perform remediation._refuse('PT422', 'That is not a share link');
  end if;
  select * into l from remediation.site_list where share_token_sha256 = remediation._sha256(p_token);
  if not found then
    perform remediation._refuse('PT404', 'This share link is not valid. Its owner may have replaced or stopped it.');
  end if;
  return jsonb_build_object(
    'name', l.name,
    'owner', remediation._display_name(l.owner_id),
    'rims_ids', coalesce((select jsonb_agg(i.rims_id order by i.seq) from remediation.site_list_item i where i.list_id = l.id), '[]'::jsonb),
    'updated_at', l.updated_at
  );
end
$$;


-- ---------------------------------------------------------------------------
-- Club weights. Decided by poll (2026-10-26): anyone signed in may change
-- any club's weights, and the history makes every change visible and
-- undoable. What these add is only what keeps the history worth reading: the
-- club must be one the analysis knows, a change must change something, and
-- one account makes at most weight_changes_per_day() a day.
-- ---------------------------------------------------------------------------

create function remediation._weights_of(w remediation.club_weights) returns jsonb
language sql immutable as $$
  select jsonb_build_object('deficit', w.deficit, 'water', w.water, 'trail', w.trail,
                            'cluster', w.cluster, 'restricted', w.restricted)
$$;

create function remediation._current_weights(club text) returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(
    (select remediation._weights_of(w) from remediation.club_weights w where w.club = _current_weights.club
      order by w.changed_at desc, w.id desc limit 1),
    remediation.default_weights())
$$;

-- Anyone may read a club's weights and their history; by_you is false for
-- someone signed out.
create function remediation.read_weights(p_club text) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'club', p_club,
    'current', remediation._current_weights(p_club),
    'defaults', remediation.default_weights(),
    'history', coalesce((
      select jsonb_agg(entry order by changed_at desc, id desc) from (
        select w.id, w.changed_at,
               remediation._weights_of(w) || jsonb_build_object(
                 'id', w.id, 'note', w.note, 'restored_from', w.restored_from,
                 'changed_by', w.changed_by_name, 'by_you', w.changed_by is not distinct from auth.uid() and auth.uid() is not null,
                 'changed_at', w.changed_at) as entry
          from remediation.club_weights w where w.club = p_club
         order by w.changed_at desc, w.id desc
         limit remediation.weights_history_limit()) recent
    ), '[]'::jsonb)
  )
$$;

create function remediation._weight(name text, value int) returns int
language plpgsql immutable as $$
begin
  if value is null or value not between 0 and 100 then
    perform remediation._refuse('PT422', 'The ' || name || ' weight must be a whole number from 0 to 100');
  end if;
  return value;
end
$$;

create function remediation._add_weights(uid uuid, club text, weights jsonb, note text, restored_from bigint) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  if not exists (select from remediation.site s where s.club = _add_weights.club) then
    perform remediation._refuse('PT422', 'No club by that name in the latest analysis');
  end if;
  if weights = remediation._current_weights(club) then
    perform remediation._refuse('PT422', 'These are already the club''s weights');
  end if;
  perform remediation._lock(uid);
  if (select count(*) from remediation.club_weights w
       where w.changed_by = uid and w.changed_at >= now() - interval '1 day') >= remediation.weight_changes_per_day() then
    perform remediation._refuse('PT429', 'One account can change weights ' || remediation.weight_changes_per_day() || ' times a day');
  end if;
  insert into remediation.club_weights (club, deficit, water, trail, cluster, restricted, note, restored_from, changed_by, changed_by_name)
  values (club, (weights ->> 'deficit')::int, (weights ->> 'water')::int, (weights ->> 'trail')::int,
          (weights ->> 'cluster')::int, (weights ->> 'restricted')::int,
          remediation._text('The note', note, 200), restored_from, uid, remediation._display_name(uid));
  return remediation.read_weights(club);
end
$$;

create function remediation.change_weights(
  p_club text, p_deficit int, p_water int, p_trail int, p_cluster int, p_restricted int, p_note text default null
) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
begin
  return remediation._add_weights(uid, remediation._text('The club', p_club, 120), jsonb_build_object(
    'deficit', remediation._weight('deficit', p_deficit), 'water', remediation._weight('water', p_water),
    'trail', remediation._weight('trail', p_trail), 'cluster', remediation._weight('cluster', p_cluster),
    'restricted', remediation._weight('restricted', p_restricted)), p_note, null);
end
$$;

-- Undo: a new entry with an earlier entry's weights, pointing back at it.
create function remediation.restore_weights(p_entry_id bigint, p_note text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
  earlier remediation.club_weights;
begin
  select * into earlier from remediation.club_weights where id = p_entry_id;
  if not found then
    perform remediation._refuse('PT404', 'No such weights entry');
  end if;
  return remediation._add_weights(uid, earlier.club, remediation._weights_of(earlier), p_note, earlier.id);
end
$$;


-- ---------------------------------------------------------------------------
-- Claims (PLAN.md §6; one person, no review, decided 2026-10-28):
--
--   claimed ──first photo──► in_progress ──mark as done──► done ──► three follow-up visits
--      │                          │
--      └── release, or due_at passes ──► released
--
-- The clock is due_at, 14 days. Done is public at once: the photos, the
-- steps, the notes, the hours and the claimer's name.
-- ---------------------------------------------------------------------------

-- The day after Labor Day (the first Monday in September) of a year: when
-- peak season ends, everywhere on the trail (decided 2026-10-28).
create function remediation._day_after_labor_day(y int) returns date
language sql immutable as $$
  select make_date(y, 9, 1) + ((8 - extract(isodow from make_date(y, 9, 1))::int) % 7) + 1
$$;

-- Sites restored recently enough that their follow-ups are still to come or
-- open: those are taken as follow-ups, not claimed again from scratch.
create function remediation._in_follow_up(rims_id text) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select from remediation.follow_up f where f.rims_id = _in_follow_up.rims_id and f.closes_on > current_date)
$$;

-- Claims this account holds now.
create function remediation._held(uid uuid) returns int
language sql stable security definer set search_path = '' as $$
  select count(*)::int from remediation.claim where claimer_id = uid and state in ('claimed', 'in_progress')
$$;

-- One site, or several at once (a site and its cluster). All or none.
create function remediation.claim_sites(p_rims_ids text[]) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
  sites text[];
  refused text;
  made jsonb := '[]'::jsonb;
  c remediation.claim;
  rims text;
begin
  if coalesce(cardinality(p_rims_ids), 0) not between 1 and remediation.sites_per_claim_request() then
    perform remediation._refuse('PT422', 'Claim between 1 and ' || remediation.sites_per_claim_request() || ' sites at once');
  end if;
  select array_agg(r order by first_seen) into sites from (
    select remediation._rims_id(r) as r, min(n) as first_seen from unnest(p_rims_ids) with ordinality as t(r, n) group by r
  ) distinct_sites;
  select string_agg(r, ', ') into refused from unnest(sites) r
   where not exists (select from remediation.site s where s.rims_id = r and s.workable);
  if refused is not null then
    perform remediation._refuse('PT422', 'Not a site the latest analysis says needs work: ' || refused);
  end if;
  select string_agg(r, ', ') into refused from unnest(sites) r where remediation._in_follow_up(r);
  if refused is not null then
    perform remediation._refuse('PT409', 'Restored already, and waiting for its follow-up visits: ' || refused);
  end if;
  perform remediation._release_overdue();
  perform remediation._lock(uid);
  if remediation._held(uid) + cardinality(sites) > remediation.live_claims_per_user() then
    perform remediation._refuse('PT409', 'One account holds at most ' || remediation.live_claims_per_user() || ' sites at a time');
  end if;
  select string_agg(cl.rims_id, ', ' order by cl.rims_id) into refused from remediation.claim cl
   where cl.rims_id = any (sites) and remediation._working(cl.state);
  if refused is not null then
    perform remediation._refuse('PT409', 'Already claimed: ' || refused);
  end if;
  begin
    foreach rims in array sites loop
      insert into remediation.claim (rims_id, claimer_id, state, due_at)
      values (rims, uid, 'claimed', now() + make_interval(days => remediation.claim_days()))
      returning * into c;
      made := made || jsonb_build_array(remediation._claim_summary(c, uid));
    end loop;
  exception when unique_violation then
    -- Someone else claimed one of them between the check and the insert.
    perform remediation._refuse('PT409', 'Someone claimed one of these sites a moment ago');
  end;
  return made;
end
$$;

-- The claim holding a site now, or null when it is open.
create function remediation.claim_for_site(p_rims_id text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
  c remediation.claim;
begin
  perform remediation._release_overdue();
  select * into c from remediation.claim
   where rims_id = remediation._rims_id(p_rims_id) and remediation._working(state);
  if not found then
    return null;
  end if;
  return remediation._claim_summary(c, uid);
end
$$;

create function remediation.my_claims() returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
begin
  perform remediation._release_overdue();
  return coalesce((
    select jsonb_agg(summary order by claimed_at desc) from (
      select remediation._claim_summary(cl, uid) as summary, cl.claimed_at
        from remediation.claim cl
       where cl.claimer_id = uid
       order by cl.claimed_at desc limit 100) mine
  ), '[]'::jsonb);
end
$$;

create function remediation.read_claim(p_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
begin
  perform remediation._release_overdue();
  if not exists (select from remediation.claim where id = p_id) then
    perform remediation._refuse('PT404', 'No such claim');
  end if;
  return remediation._claim_detail(p_id, uid);
end
$$;

create function remediation.release_claim(p_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
begin
  perform remediation._release_overdue();
  perform remediation._own_claim(p_id, uid);
  update remediation.claim set state = 'released', released_at = now() where id = p_id;
  return remediation._claim_detail(p_id, uid);
end
$$;


-- ---------------------------------------------------------------------------
-- Follow-up visits
-- ---------------------------------------------------------------------------

-- One definition of how a follow-up stands, in the open view below.
create function remediation._follow_up_state(f remediation.follow_up) returns text
language plpgsql stable security definer set search_path = '' as $$
begin
  return (select v.state from remediation.open_follow_ups v where v.id = f.id);
end
$$;

create function remediation._follow_up_json(f remediation.follow_up) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'id', f.id, 'rims_id', f.rims_id, 'done_claim_id', f.done_claim_id, 'visit', f.visit,
    'opens_on', f.opens_on, 'closes_on', f.closes_on,
    'state', remediation._follow_up_state(f)
  )
$$;

-- Makes a done restoration's three follow-up visits.
create function remediation._schedule_follow_ups(c remediation.claim) returns void
language plpgsql security definer set search_path = '' as $$
declare
  first_year int := extract(year from c.done_at)::int;
  n int;
begin
  if remediation._day_after_labor_day(first_year) <= c.done_at::date then
    first_year := first_year + 1;
  end if;
  for n in 1..3 loop
    insert into remediation.follow_up (rims_id, done_claim_id, visit, opens_on, closes_on)
    values (c.rims_id, c.id, n,
            remediation._day_after_labor_day(first_year + n - 1),
            remediation._day_after_labor_day(first_year + n));
  end loop;
end
$$;

-- A site's follow-up visits, from its latest restoration.
create function remediation.site_follow_ups(p_rims_id text) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  perform remediation._caller();
  perform remediation._release_overdue();
  return coalesce((
    select jsonb_agg(remediation._follow_up_json(f) order by f.visit)
      from remediation.follow_up f
     where f.done_claim_id = (
       select c.id from remediation.claim c
        where c.rims_id = remediation._rims_id(p_rims_id) and c.state = 'done' and c.follow_up_id is null
        order by c.done_at desc limit 1)
  ), '[]'::jsonb);
end
$$;

-- Anyone may take an open follow-up: a claim of its own, for claim_days().
create function remediation.take_follow_up(p_follow_up_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
  f remediation.follow_up;
  c remediation.claim;
begin
  perform remediation._release_overdue();
  select * into f from remediation.follow_up where id = p_follow_up_id for update;
  if not found then
    perform remediation._refuse('PT404', 'No such follow-up visit');
  end if;
  case remediation._follow_up_state(f)
    when 'waiting' then perform remediation._refuse('PT409', 'This visit opens on ' || to_char(f.opens_on, 'FMMonth FMDD, YYYY'));
    when 'taken' then perform remediation._refuse('PT409', 'Someone has taken this visit');
    when 'done' then perform remediation._refuse('PT409', 'This visit is done');
    when 'missed' then perform remediation._refuse('PT409', 'This visit closed on ' || to_char(f.closes_on, 'FMMonth FMDD, YYYY'));
    else null;
  end case;
  perform remediation._lock(uid);
  if remediation._held(uid) + 1 > remediation.live_claims_per_user() then
    perform remediation._refuse('PT409', 'One account holds at most ' || remediation.live_claims_per_user() || ' sites at a time');
  end if;
  begin
    insert into remediation.claim (rims_id, claimer_id, state, due_at, follow_up_id)
    values (f.rims_id, uid, 'claimed', now() + make_interval(days => remediation.claim_days()), f.id)
    returning * into c;
  exception when unique_violation then
    perform remediation._refuse('PT409', 'Someone is working on this site now');
  end;
  return remediation._claim_summary(c, uid);
end
$$;


-- ---------------------------------------------------------------------------
-- Photos. The phone uploads the JPEG to the private remediation-photos bucket
-- first, at `<claim id>/<its id for the photo>.jpg` (the bucket's insert
-- policy, below, lets only the claimer upload, while the claim is open),
-- then calls add_photo() to put it on the claim.
--
-- The phone redraws every photo before it leaves, which strips the location
-- a camera writes into it (web/src/photo.ts). With no server in between,
-- nothing redraws it again: the old API did, against a phone that had been
-- tampered with (the review's finding 6). What remains is the bucket's own
-- type and size limits, set below.
--
-- The bucket is private, so the policies below are who may read a photo,
-- and a Storage link to one (a signed URL) is made by someone they let read
-- it. A link outlives the access it was made with until it expires; Storage
-- checks only its signature. So these are the limits on what one account can
-- put where anyone holding a link can fetch it, and not a promise that a
-- photo stops being reachable the moment a claim closes.
-- ---------------------------------------------------------------------------

-- An object's claim and photo id, from its name in the bucket; both null for
-- a name that is not a photo's. The pattern is checked before any cast, so a
-- stray name makes a policy refuse rather than raise.
create function remediation._photo_object(object_name text, out claim_id uuid, out client_id text)
language sql immutable set search_path = '' as $$
  select case when object_name ~ remediation.photo_object_pattern() then split_part(object_name, '/', 1)::uuid end,
         case when object_name ~ remediation.photo_object_pattern() then left(split_part(object_name, '/', 2), -4) end
$$;

-- This account's objects on its claims still being worked that are not on
-- their claim yet and never were: no photo uses them and no photo receipt
-- names them. One left by a claim that has closed stops counting, so a phone
-- that lost a few answers is not locked out for good.
create function remediation._pending_uploads(uid uuid) returns int
language sql stable security definer set search_path = '' as $$
  select count(*)::int
    from remediation.claim c
    join storage.objects o on o.bucket_id = 'remediation-photos' and o.name like c.id::text || '/%'
    cross join lateral remediation._photo_object(o.name) n
   where c.claimer_id = uid and remediation._working(c.state)
     and not exists (select from remediation.photo p where p.object_name = o.name)
     and not exists (select from remediation.photo_receipt r where r.claim_id = n.claim_id and r.client_id = n.client_id)
$$;

-- What this account has uploaded in the last day, to any of its claims.
create function remediation._uploads_today(uid uuid) returns int
language sql stable security definer set search_path = '' as $$
  select count(*)::int
    from remediation.claim c
    join storage.objects o on o.bucket_id = 'remediation-photos' and o.name like c.id::text || '/%'
   where c.claimer_id = uid and o.created_at > now() - interval '1 day'
$$;

-- The bucket's insert policy asks this: the claimer of a claim still being
-- worked and not overdue, within the claim's object cap and their own (the
-- sixth pass, finding 1).
--
-- The caps count, then Storage inserts, so uploads whose last steps overlap
-- all see the same count (the re-check's new problem 1). A lock here cannot
-- close that: Storage asks this policy in a savepoint it rolls back before
-- writing the row as its own role (supabase/storage, src/storage/uploader.ts,
-- completeUpload, read 2026-10-27), and a lock taken in a savepoint is
-- released at the rollback (measured on Postgres 16, 2026-10-27). Reasoned,
-- not measured against Storage: Storage sends the bytes before that last
-- transaction, which is a few queries long, so only uploads finishing at
-- the same moment slip past a cap together, at most as many as Storage has
-- database connections, and every count after them includes them.
create function remediation.may_upload_photo(object_name text) returns boolean
language plpgsql stable security definer set search_path = '' as $$
declare
  uid uuid := auth.uid();
  o record;
begin
  if uid is null or coalesce((auth.jwt() ->> 'is_anonymous')::boolean, false) then
    return false;
  end if;
  select * into o from remediation._photo_object(object_name);
  return o.claim_id is not null
     and exists (
           select from remediation.claim c
            where c.id = o.claim_id and c.claimer_id = uid and remediation._working(c.state) and c.due_at >= now())
     and (select count(*) from storage.objects s
           where s.bucket_id = 'remediation-photos' and s.name like o.claim_id::text || '/%') < remediation.objects_per_claim()
     and remediation._pending_uploads(uid) < remediation.pending_uploads_per_user()
     and remediation._uploads_today(uid) < remediation.uploads_per_user_per_day();
end
$$;

-- The bucket's delete policy asks this: the claimer of a claim still being
-- worked may delete an object that was put on the claim and that no photo
-- uses now, because it was replaced or removed.
create function remediation.may_delete_photo_object(object_name text) returns boolean
language plpgsql stable security definer set search_path = '' as $$
declare
  uid uuid := auth.uid();
  o record;
begin
  select * into o from remediation._photo_object(object_name);
  if uid is null or o.claim_id is null then
    return false;
  end if;
  return exists (
           select from remediation.claim c
            where c.id = o.claim_id and remediation._working(c.state) and c.claimer_id = uid)
     and exists (select from remediation.photo_receipt r where r.claim_id = o.claim_id and r.client_id = o.client_id)
     and not exists (select from remediation.photo p where p.object_name = may_delete_photo_object.object_name);
end
$$;

-- The bucket's select policy asks this, signed in or not: who may download
-- a photo, and so who may make a link to one. A photo on done work is open
-- data, like the claimer's name; until then it is the claimer's. An object
-- no photo uses is nobody's to read, except as the delete policy needs:
-- Storage reads a row before it deletes it (the sixth pass, finding 1).
create function remediation.may_read_photo_object(object_name text) returns boolean
language plpgsql stable security definer set search_path = '' as $$
declare
  uid uuid := auth.uid();
  state text;
  claimer uuid;
begin
  select c.state, c.claimer_id into state, claimer
    from remediation.photo p join remediation.claim c on c.id = p.claim_id
   where p.object_name = may_read_photo_object.object_name;
  if state is null then
    return remediation.may_delete_photo_object(object_name);
  end if;
  return state = 'done' or (uid is not null and claimer = uid);
end
$$;

-- The claimer's phone already delivered this photo. Asked before the
-- claim's state: a photo that arrived before the claim was marked done is
-- still there afterwards, and the phone should hear that, not a refusal.
create function remediation._sent_before(claim_id uuid, uid uuid, client_id text) returns boolean
language sql stable security definer set search_path = '' as $$
  select client_id is not null
     and exists (select from remediation.claim c where c.id = _sent_before.claim_id and c.claimer_id = uid)
     and exists (select from remediation.photo_receipt r where r.claim_id = _sent_before.claim_id and r.client_id = _sent_before.client_id)
$$;

-- `p_replaces`, for a before or after photo the phone queued with no signal:
-- the id of the photo in its slot when it was taken, or 'nothing'. If the
-- slot holds anything else now, the photo is refused with PT412 rather than
-- put over the newer one; the phone keeps it. One person's claim can still
-- have two phones. Phones' clocks are not trusted to say which photo is newer.
-- A follow-up takes after photos and extras only: it re-photographs the points.
create function remediation.add_photo(
  p_claim_id uuid, p_phase text, p_point int, p_client_id text, p_replaces text default null
) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
  c remediation.claim;
  object_path text;
  current_id uuid;
  replaced text;
begin
  if p_phase is null or p_phase not in ('before', 'after', 'extra')
     or (p_phase = 'extra') <> (p_point is null) or (p_point is not null and p_point not in (1, 2)) then
    perform remediation._refuse('PT422', 'A before or after photo needs photo point 1 or 2; an extra needs none');
  end if;
  if p_client_id is null or p_client_id !~ remediation.client_id_pattern() then
    perform remediation._refuse('PT422', 'That is not a photo id');
  end if;
  if p_replaces is not null and p_replaces !~ '^(nothing|[0-9a-f-]{36})$' then
    perform remediation._refuse('PT422', 'That is not a photo id');
  end if;
  perform remediation._release_overdue();
  c := remediation._claim_for_update(p_claim_id);
  if remediation._sent_before(c.id, uid, p_client_id) then
    return remediation._claim_detail(c.id, uid);
  end if;
  c := remediation._own_claim(p_claim_id, uid);
  if p_phase = 'before' and c.follow_up_id is not null then
    perform remediation._refuse('PT422', 'A follow-up visit takes the after photos again, not before photos');
  end if;
  object_path := c.id::text || '/' || p_client_id || '.jpg';
  if not exists (select from storage.objects o where o.bucket_id = 'remediation-photos' and o.name = object_path) then
    perform remediation._refuse('PT422', 'The photo has not arrived. Send it again.');
  end if;
  if (select count(*) from remediation.photo p where p.claim_id = c.id) >= remediation.photos_per_claim() then
    perform remediation._refuse('PT409', 'A claim holds at most ' || remediation.photos_per_claim() || ' photos');
  end if;
  if p_point is not null then
    select p.id, p.object_name into current_id, replaced
      from remediation.photo p where p.claim_id = c.id and p.phase = p_phase and p.point = p_point;
    if p_replaces is not null and p_replaces <> coalesce(current_id::text, 'nothing') then
      perform remediation._refuse('PT412',
        'This point has a newer photo than this phone had seen when it took this one, so it was not put over it');
    end if;
    delete from remediation.photo p where p.claim_id = c.id and p.phase = p_phase and p.point = p_point;
  end if;
  insert into remediation.photo (claim_id, phase, point, object_name) values (c.id, p_phase, p_point, object_path);
  insert into remediation.photo_receipt (claim_id, client_id) values (c.id, p_client_id);
  -- The first photo starts the work: a before photo for a restoration, any
  -- photo for a follow-up, which has no before.
  if c.state = 'claimed' and (p_phase = 'before' or c.follow_up_id is not null) then
    update remediation.claim set state = 'in_progress', started_at = now() where id = c.id;
  end if;
  -- The object the new photo replaced, which no photo uses now: the app
  -- deletes it, so a retake (someone was in the frame) does not become
  -- public when the work is done.
  return remediation._claim_detail(c.id, uid) || jsonb_build_object('unused_path', replaced);
end
$$;

-- The photo comes off the claim, and the answer names its object, which
-- may_delete_photo_object() now lets the claimer delete and the app does.
create function remediation.remove_photo(p_claim_id uuid, p_photo_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
  removed text;
begin
  perform remediation._release_overdue();
  perform remediation._own_claim(p_claim_id, uid);
  delete from remediation.photo where id = p_photo_id and claim_id = p_claim_id returning object_name into removed;
  if removed is null then
    perform remediation._refuse('PT404', 'No such photo on this claim');
  end if;
  return remediation._claim_detail(p_claim_id, uid) || jsonb_build_object('unused_path', removed);
end
$$;


-- ---------------------------------------------------------------------------
-- Hours, and marking the work done
-- ---------------------------------------------------------------------------

-- Your hours on this claim, across all your visits to the site, in half hours.
create function remediation.log_hours(p_claim_id uuid, p_hours numeric) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
begin
  if p_hours is null or p_hours <= 0 or p_hours > remediation.hours_max() or (p_hours * 2) <> trunc(p_hours * 2) then
    perform remediation._refuse('PT422', 'Hours are in half hours, from 0.5 to ' || remediation.hours_max());
  end if;
  perform remediation._release_overdue();
  perform remediation._own_claim(p_claim_id, uid);
  update remediation.claim set hours_tenths = (p_hours * 10)::int where id = p_claim_id;
  return remediation._claim_detail(p_claim_id, uid);
end
$$;

-- What the claim still needs before it can be marked done: a before and an
-- after at each photo point for a restoration, a new after at each for a
-- follow-up.
create function remediation._missing_photos(c remediation.claim) returns text
language sql stable security definer set search_path = '' as $$
  select string_agg(phase || ' at point ' || point, ', ' order by point, phase desc)
    from (values ('before', 1), ('after', 1), ('before', 2), ('after', 2)) need(phase, point)
   where (need.phase = 'after' or c.follow_up_id is null)
     and not exists (
       select from remediation.photo p where p.claim_id = c.id and p.phase = need.phase and p.point = need.point)
$$;

-- Marks the work done. It is public at once (decided 2026-10-28: no review),
-- and a restoration's three follow-up visits are scheduled.
create function remediation.finish_claim(p_id uuid, p_steps_done text[] default '{}', p_notes text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
  c remediation.claim;
  missing text;
  steps text[] := '{}';
  step text;
begin
  if coalesce(cardinality(p_steps_done), 0) > 20 then
    perform remediation._refuse('PT422', 'At most 20 steps');
  end if;
  foreach step in array coalesce(p_steps_done, '{}') loop
    step := remediation._text('A step', step, 120);
    if not (step = any (steps)) then
      steps := steps || step;
    end if;
  end loop;
  perform remediation._release_overdue();
  c := remediation._own_claim(p_id, uid, array['in_progress']);
  missing := remediation._missing_photos(c);
  if missing is not null then
    perform remediation._refuse('PT422', 'Still needed before it is done: ' || missing);
  end if;
  update remediation.claim
     set steps_done = steps, notes = remediation._text('The notes', p_notes, 1000, true),
         state = 'done', done_at = now()
   where id = p_id
  returning * into c;
  if c.follow_up_id is null then
    perform remediation._schedule_follow_ups(c);
  end if;
  return remediation._claim_detail(p_id, uid);
end
$$;

create function remediation.my_hours() returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := remediation._caller();
begin
  perform remediation._release_overdue();
  return (
    select jsonb_build_object(
      'done', coalesce(sum(hours_tenths) filter (where state = 'done'), 0) / 10.0,
      'in_progress', coalesce(sum(hours_tenths) filter (where remediation._working(state)), 0) / 10.0,
      'claims', count(*) filter (where state = 'done'))
      from remediation.claim where claimer_id = uid
  );
end
$$;


-- ---------------------------------------------------------------------------
-- What is open: anyone may read these, through Supabase's REST API with the
-- public key, or as the files the analysis job publishes beside sites.json.
-- They read the tables as their owner, so they are the whole of what an
-- anonymous reader sees. Names appear only on done work.
-- ---------------------------------------------------------------------------

create view remediation.open_claims as
select c.id,
       c.rims_id,
       case when c.follow_up_id is null then 'restore' else 'follow_up' end as kind,
       (select f.visit from remediation.follow_up f where f.id = c.follow_up_id) as visit,
       case when c.state in ('claimed', 'in_progress') and c.due_at < now() then 'released' else c.state end as state,
       c.claimed_at,
       case when c.state in ('claimed', 'in_progress') and c.due_at >= now() then c.due_at end as due_at,
       c.done_at,
       coalesce(c.released_at, case when c.state in ('claimed', 'in_progress') and c.due_at < now() then c.due_at end) as released_at,
       case when c.state = 'done' then (select p.display_name from remediation.profile p where p.user_id = c.claimer_id) end as claimer,
       case when c.state = 'done' then c.steps_done end as steps_done,
       case when c.state = 'done' then c.hours_tenths / 10.0 end as hours
  from remediation.claim c;

-- The before and after photos of done work.
create view remediation.open_photos as
select p.claim_id, c.rims_id, p.phase, p.point, p.object_name as path, p.created_at
  from remediation.photo p join remediation.claim c on c.id = p.claim_id
 where c.state = 'done';

-- Every follow-up visit: when it opens and closes, and how it stands.
create view remediation.open_follow_ups as
select f.id, f.rims_id, f.done_claim_id, f.visit, f.opens_on, f.closes_on,
       case
         when exists (select from remediation.claim c where c.follow_up_id = f.id and c.state = 'done') then 'done'
         when exists (select from remediation.claim c
                       where c.follow_up_id = f.id and c.state in ('claimed', 'in_progress') and c.due_at >= now()) then 'taken'
         when current_date < f.opens_on then 'waiting'
         when current_date < f.closes_on then 'open'
         else 'missed'
       end as state
  from remediation.follow_up f;

create view remediation.open_weights as
select w.id, w.club, w.deficit, w.water, w.trail, w.cluster, w.restricted, w.note, w.restored_from,
       w.changed_by_name as changed_by, w.changed_at
  from remediation.club_weights w;


-- ---------------------------------------------------------------------------
-- The analysis job's load: the latest sites, replacing the last load.
-- ---------------------------------------------------------------------------

-- `p_sites` is sites.json's records; a site is workable when its action is
-- one a volunteer claims (close_restore or harden), as the old API read it.
-- Refuses a load with fewer than half the sites, or half the workable sites,
-- of the largest load of the last 30 days: a truncated or broken file, or a
-- scorer that stopped calling sites workable, would otherwise empty the list
-- every claim is checked against. Measured against the largest in a window
-- of time, not of loads, so no run of loads walks it down by halves, however
-- fast (the sixth pass, finding 4, and its re-check: 120 calls in a second
-- took 3,442 sites to 1 against a window of the last ten loads). A leaked
-- loader login can halve the list once a month at most. `@unvalidated`, the
-- half and the 30 days: ATC's inventory changed by a handful of sites a week
-- while this was built, and nothing has measured a real month of loads.
create function remediation.load_sites(p_sites jsonb) returns int
language plpgsql security definer set search_path = '' as $$
declare
  incoming int;
  incoming_workable int;
  most int;
  most_workable int;
begin
  if jsonb_typeof(p_sites) is distinct from 'array' then
    raise exception 'sites.json is not a list of sites';
  end if;
  select count(*), count(*) filter (where workable) into incoming, incoming_workable
    from (select distinct on (r ->> 'rims_id') coalesce(r ->> 'action', '') in ('close_restore', 'harden') as workable
            from jsonb_array_elements(p_sites) r
           where jsonb_typeof(r) = 'object' and (r ->> 'rims_id') ~ remediation.rims_id_pattern()) arriving;
  select greatest(coalesce(max(recent.sites), 0), (select count(*) from remediation.site)),
         greatest(coalesce(max(recent.workable), 0), (select count(*) from remediation.site where workable))
    into most, most_workable
    from (select l.sites, l.workable from remediation.site_load l where l.loaded_at > now() - interval '30 days') recent;
  if incoming = 0 or incoming < most / 2 or incoming_workable < most_workable / 2 then
    raise exception 'sites.json names % sites, % of them workable, where recent loads held up to % and %; refusing to replace them',
      incoming, incoming_workable, most, most_workable;
  end if;
  with arriving as (
    select distinct on (r ->> 'rims_id')
           r ->> 'rims_id' as rims_id,
           nullif(r ->> 'club', '') as club,
           coalesce(r ->> 'action', '') in ('close_restore', 'harden') as workable
      from jsonb_array_elements(p_sites) r
     where jsonb_typeof(r) = 'object' and (r ->> 'rims_id') ~ remediation.rims_id_pattern()
  ), kept as (
    insert into remediation.site (rims_id, club, workable, loaded_at)
    select rims_id, club, workable, now() from arriving
    on conflict (rims_id) do update set club = excluded.club, workable = excluded.workable, loaded_at = excluded.loaded_at
    returning rims_id
  )
  delete from remediation.site s where not exists (select from arriving a where a.rims_id = s.rims_id);
  insert into remediation.site_load (sites, workable) values (incoming, incoming_workable);
  -- By age, not count: a count would let a burst of loads push the largest out.
  delete from remediation.site_load where loaded_at < now() - interval '90 days';
  return incoming;
end
$$;


-- ---------------------------------------------------------------------------
-- Photos bucket
-- ---------------------------------------------------------------------------

-- Private: a photo is read through the select policy below, which is what
-- keeps the bucket from being anyone's free file host on OurHike's project
-- (the sixth pass, finding 1). Only JPEGs, at most 3 MB, which is what the
-- app sends (2048 px on the long side at quality 0.85 is typically under
-- 1 MB). The Storage service enforces both, not Postgres.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('remediation-photos', 'remediation-photos', false, 3145728, array['image/jpeg'])
on conflict (id) do update
  set public = excluded.public, file_size_limit = excluded.file_size_limit, allowed_mime_types = excluded.allowed_mime_types;

create policy "remediation: claimers upload photos to their open claims"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'remediation-photos' and remediation.may_upload_photo(name));

create policy "remediation: a photo is read by its claimer, and by anyone once done"
  on storage.objects for select to anon, authenticated
  using (bucket_id = 'remediation-photos' and remediation.may_read_photo_object(name));

create policy "remediation: claimers delete objects no photo uses"
  on storage.objects for delete to authenticated
  using (bucket_id = 'remediation-photos' and remediation.may_delete_photo_object(name));
-- No update policy: an uploaded object is never overwritten.


-- ---------------------------------------------------------------------------
-- Grants. Everything else stays revoked: explicitly, in case a project's
-- default privileges reach this schema as Supabase's reach `public`.
-- ---------------------------------------------------------------------------

revoke all on all tables in schema remediation from public, anon, authenticated;
revoke all on all sequences in schema remediation from public, anon, authenticated;
revoke all on all functions in schema remediation from public, anon, authenticated;

grant select on remediation.open_claims, remediation.open_photos, remediation.open_follow_ups, remediation.open_weights
  to anon, authenticated;
grant execute on function remediation.read_weights(text), remediation.may_read_photo_object(text) to anon, authenticated;
grant execute on function remediation.may_upload_photo(text), remediation.may_delete_photo_object(text) to authenticated;
grant execute on function
  remediation.me(), remediation.set_display_name(text), remediation.delete_my_data(),
  remediation.my_lists(), remediation.read_list(uuid), remediation.create_list(text, text[]), remediation.rename_list(uuid, text),
  remediation.delete_list(uuid), remediation.add_to_list(uuid, text), remediation.remove_from_list(uuid, text),
  remediation.share_list(uuid), remediation.unshare_list(uuid), remediation.open_shared_list(text),
  remediation.change_weights(text, int, int, int, int, int, text), remediation.restore_weights(bigint, text),
  remediation.claim_sites(text[]), remediation.claim_for_site(text), remediation.my_claims(), remediation.read_claim(uuid),
  remediation.release_claim(uuid), remediation.site_follow_ups(text), remediation.take_follow_up(uuid),
  remediation.add_photo(uuid, text, int, text, text), remediation.remove_photo(uuid, uuid),
  remediation.log_hours(uuid, numeric), remediation.finish_claim(uuid, text[], text), remediation.my_hours()
  to authenticated;
grant execute on function remediation.load_sites(jsonb) to remediation_loader;
