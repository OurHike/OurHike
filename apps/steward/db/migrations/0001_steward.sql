-- Campsite Steward's data, in OurHike's Supabase project (#1906, #1910; PLAN.md,
-- decided 2026-10-27: "no API server: the app talks to Supabase directly").
--
-- How it is put together:
--   - Every table is in the `steward` schema, with row-level security on and no
--     grant to anon or authenticated: nothing reaches a table directly.
--   - Every change goes through a function below. Each is SECURITY DEFINER with
--     an empty search_path, checks who is calling, and carries the rule the old
--     Python API carried (apps/steward/api, retired by this change). Their
--     messages are the ones the web app shows.
--   - Errors carry an HTTP status as SQLSTATE PTnnn, which PostgREST turns into
--     that status: PT401 sign in, PT403 not yours, PT404 no such thing,
--     PT409 not in this state or over a cap, PT412 the slot changed,
--     PT422 not acceptable, PT429 too many today.
--   - What is open, anyone may read: the open_* views, which carry names only
--     on verified work (decided 2026-10-27, by poll: "the public sees that a
--     site is claimed and when it is due, not who will be out there").
--   - Photos live in the public Storage bucket `steward-photos`, under
--     `<claim id>/<the phone's id for the photo>.jpg`.

create schema if not exists steward;
revoke all on schema steward from public;
grant usage on schema steward to anon, authenticated;
-- Postgres lets PUBLIC execute every new function. Nothing here may be
-- executed unless it is granted by name below.
alter default privileges in schema steward revoke execute on functions from public;

-- The analysis job loads the latest list of sites through load_sites() and
-- nothing else (apps/steward/db/README.md: give it a login of its own).
do $$
begin
  if not exists (select from pg_roles where rolname = 'steward_loader') then
    create role steward_loader nologin;
  end if;
end
$$;
grant usage on schema steward to steward_loader;


-- ---------------------------------------------------------------------------
-- Limits. `@unvalidated`, all of them, carried over from the old API's
-- limits.py: picked to sit well above what a club volunteer is expected to do
-- and far below what would let one account fill the database. Nobody has
-- measured real use; the numbers to compare against, once there is some, are
-- the largest list, the busiest weights history and the longest crew.
-- ---------------------------------------------------------------------------

create function steward.claim_days() returns int language sql immutable as 'select 14';
-- Days a crew gets after a send-back, at least: PLAN.md stops the clock at
-- Submitted and says nothing about restarting it.
create function steward.send_back_days() returns int language sql immutable as 'select 7';
-- Days whoever rejects a claim waits before claiming that site (the review's N2).
create function steward.rejecter_wait_days() returns int language sql immutable as 'select 30';
-- Sites one account holds at once, counting submitted claims, which hold
-- their sites too (the review's finding 2). High enough for a cluster: most
-- are 2-3 sites (2026-10-26).
create function steward.live_claims_per_user() returns int language sql immutable as 'select 10';
create function steward.sites_per_claim_request() returns int language sql immutable as 'select 10';
create function steward.crew_max() returns int language sql immutable as 'select 12';
create function steward.photos_per_claim() returns int language sql immutable as 'select 40';
-- Objects one claim's folder may hold in the bucket: photos replaced or
-- removed stay until the crew deletes them, so twice the photo cap.
create function steward.objects_per_claim() returns int language sql immutable as 'select 80';
create function steward.hours_max() returns int language sql immutable as 'select 72';
create function steward.lists_per_user() returns int language sql immutable as 'select 50';
create function steward.items_per_list() returns int language sql immutable as 'select 500';
create function steward.weight_changes_per_day() returns int language sql immutable as 'select 30';
create function steward.weights_history_limit() returns int language sql immutable as 'select 50';
-- The need score's defaults: apps/steward/pipeline/steward_analysis/rules.py
-- DEFAULT_WEIGHTS, which a test holds equal to this.
create function steward.default_weights() returns jsonb language sql immutable as
  $$ select '{"deficit": 60, "water": 12, "trail": 6, "cluster": 8, "restricted": 10}'::jsonb $$;

-- ATC's RIMS_ID: all 3,442 are 36-character GUIDs (2026-10-27); this leaves
-- room for a format change without accepting markup.
create function steward.rims_id_pattern() returns text language sql immutable as $$ select '^[A-Za-z0-9-]{1,64}$' $$;
-- The phone's id for a photo (web/src/offline.ts newPhotoId).
create function steward.client_id_pattern() returns text language sql immutable as $$ select '^[A-Za-z0-9_-]{1,64}$' $$;
create function steward.photo_object_pattern() returns text language sql immutable as
  $$ select '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/[A-Za-z0-9_-]{1,64}\.jpg$' $$;


-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

-- The latest analysis's sites: which may be claimed, and which clubs exist.
-- Written only by load_sites().
create table steward.site (
  rims_id text primary key check (rims_id ~ '^[A-Za-z0-9-]{1,64}$'),
  club text,
  workable boolean not null,
  loaded_at timestamptz not null default now()
);
create index site_club on steward.site (club);

create table steward.profile (
  user_id uuid primary key references auth.users (id) on delete cascade,
  display_name text check (char_length(display_name) between 1 and 40),
  -- Set by delete_my_data(). The row stays, so the history that points at it
  -- still does (the review's finding 3); signing in again clears it.
  deleted_at timestamptz,
  created_at timestamptz not null default now()
);

create table steward.site_list (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references steward.profile (user_id) on delete cascade,
  name text not null check (char_length(name) between 1 and 80),
  share_token_sha256 text unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index site_list_owner on steward.site_list (owner_id);

create table steward.site_list_item (
  list_id uuid not null references steward.site_list (id) on delete cascade,
  rims_id text not null check (rims_id ~ '^[A-Za-z0-9-]{1,64}$'),
  seq bigint generated always as identity,
  primary key (list_id, rims_id)
);

create table steward.club_weights (
  id bigint generated always as identity primary key,
  club text not null check (char_length(club) between 1 and 120),
  deficit int not null check (deficit between 0 and 100),
  water int not null check (water between 0 and 100),
  trail int not null check (trail between 0 and 100),
  cluster int not null check (cluster between 0 and 100),
  restricted int not null check (restricted between 0 and 100),
  note text check (char_length(note) between 1 and 200),
  restored_from bigint references steward.club_weights (id),
  changed_by uuid references steward.profile (user_id) on delete set null,
  -- The name its changer used at the time, so a rename cannot rewrite the
  -- history (the review's finding 10). Cleared by delete_my_data().
  changed_by_name text,
  changed_at timestamptz not null default now()
);
create index club_weights_club_changed on steward.club_weights (club, changed_at desc, id desc);
create index club_weights_changed_by on steward.club_weights (changed_by, changed_at);

create table steward.claim (
  id uuid primary key default gen_random_uuid(),
  rims_id text not null check (rims_id ~ '^[A-Za-z0-9-]{1,64}$'),
  claimer_id uuid references steward.profile (user_id) on delete set null,
  state text not null check (state in ('claimed', 'in_progress', 'submitted', 'verified', 'released')),
  claimed_at timestamptz not null default now(),
  due_at timestamptz not null,
  started_at timestamptz,
  submitted_at timestamptz,
  -- After photos older than this do not count toward the next submission.
  sent_back_at timestamptz,
  verified_at timestamptz,
  released_at timestamptz,
  steps_done text[] not null default '{}',
  notes text,
  review_note text,
  reviewed_by uuid references steward.profile (user_id) on delete set null,
  reviewed_by_name text,
  rejected_by uuid references steward.profile (user_id) on delete set null,
  invite_token_sha256 text unique
);
-- One claim holds a site at a time; it is what refuses the second of two
-- claims made at the same moment.
create unique index claim_one_holder_per_site on steward.claim (rims_id)
  where state in ('claimed', 'in_progress', 'submitted');
create index claim_state_due on steward.claim (state, due_at);

create table steward.claim_member (
  claim_id uuid not null references steward.claim (id) on delete cascade,
  user_id uuid not null references steward.profile (user_id) on delete cascade,
  joined_at timestamptz not null default now(),
  -- Set when the person deletes their data. A left place gives no access and
  -- is not listed, but still bars its holder from reviewing the claim (the
  -- review's third pass, N7).
  left_at timestamptz,
  primary key (claim_id, user_id)
);
create index claim_member_user on steward.claim_member (user_id);

create table steward.photo (
  id uuid primary key default gen_random_uuid(),
  claim_id uuid not null references steward.claim (id) on delete cascade,
  phase text not null check (phase in ('before', 'after', 'extra')),
  point int check (point in (1, 2)),
  -- Its name in the steward-photos bucket.
  object_name text not null,
  uploaded_by uuid references steward.profile (user_id) on delete set null,
  created_at timestamptz not null default now(),
  check ((phase = 'extra') = (point is null))
);
-- One before and one after per photo point; a new one replaces it.
create unique index photo_one_per_slot on steward.photo (claim_id, phase, point) where point is not null;

-- Every photo a claim has received, by the phone's id for it, kept after the
-- photo is replaced or removed, so a phone sending it again after a lost
-- answer stores nothing new and brings nothing back (the third pass's P2,
-- the fourth pass's C).
create table steward.photo_receipt (
  claim_id uuid not null references steward.claim (id) on delete cascade,
  client_id text not null,
  received_at timestamptz not null default now(),
  primary key (claim_id, client_id)
);

create table steward.hours (
  claim_id uuid not null references steward.claim (id) on delete cascade,
  user_id uuid not null references steward.profile (user_id) on delete cascade,
  tenths int not null check (tenths > 0 and tenths <= 720),
  verified boolean not null default false,
  primary key (claim_id, user_id)
);

alter table steward.site enable row level security;
alter table steward.profile enable row level security;
alter table steward.site_list enable row level security;
alter table steward.site_list_item enable row level security;
alter table steward.club_weights enable row level security;
alter table steward.claim enable row level security;
alter table steward.claim_member enable row level security;
alter table steward.photo enable row level security;
alter table steward.photo_receipt enable row level security;
alter table steward.hours enable row level security;


-- ---------------------------------------------------------------------------
-- Helpers. Not granted to anyone: only the functions below call them.
-- ---------------------------------------------------------------------------

create function steward._refuse(code text, message text) returns void
language plpgsql as $$
begin
  raise exception using errcode = code, message = message;
end
$$;

-- The signed-in caller, made a profile on first use. Refuses Supabase's
-- anonymous sign-ins, which anyone can mint without an address.
create function steward._caller() returns uuid
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := auth.uid();
begin
  if uid is null or coalesce((auth.jwt() ->> 'is_anonymous')::boolean, false) then
    perform steward._refuse('PT401', 'Sign in first.');
  end if;
  insert into steward.profile (user_id) values (uid) on conflict (user_id) do nothing;
  -- Back after deleting their data: an empty account, which is what the
  -- delete left (the review's re-check, N7).
  update steward.profile set deleted_at = null where user_id = uid and deleted_at is not null;
  return uid;
end
$$;

-- Holds the caller's profile row until the transaction ends, so a cap
-- counted next still holds when the insert lands.
create function steward._lock(uid uuid) returns void
language sql security definer set search_path = '' as $$
  select null from steward.profile where user_id = uid for update;
$$;

-- A person's text: trimmed, bounded, and free of control characters and the
-- invisible format characters a name can use to pass for another (bidi
-- overrides, zero-width joiners, private use; the review's finding 10). The
-- old API refused Unicode categories Cc, Cf, Co, Cs and Cn by name; Postgres
-- regular expressions have no category classes, so these are the ranges
-- written out, and unassigned code points (Cn) are not refused.
create function steward._text(label text, value text, max_length int, multiline boolean default false) returns text
language plpgsql immutable as $$
declare
  v text := btrim(value, E' \t\r\n');
  checked text;
begin
  if value is null then
    return null;
  end if;
  if v = '' then
    perform steward._refuse('PT422', label || ' must not be empty');
  end if;
  if char_length(v) > max_length then
    perform steward._refuse('PT422', label || ' must be at most ' || max_length || ' characters');
  end if;
  checked := case when multiline then regexp_replace(v, E'\r?\n', ' ', 'g') else v end;
  if checked ~ '[\x01-\x1f\x7f-\x9f­؜᠎​-‏‪-‮⁠-⁯﻿￹-￻-\U000f0000-\U0010ffff]' then
    perform steward._refuse('PT422', label || ' must not contain control or invisible formatting characters');
  end if;
  return v;
end
$$;

create function steward._sha256(token text) returns text
language sql immutable as $$ select encode(sha256(convert_to(token, 'UTF8')), 'hex') $$;

-- 64 hex characters, from two random UUIDs: 244 random bits.
create function steward._token() returns text
language sql volatile as $$
  select replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', '')
$$;

-- Every working claim whose clock has run out goes back to Open. Not a
-- scheduled job: everything that reads or changes claims calls this first,
-- and the open views work the same state out for themselves.
create function steward._release_overdue() returns void
language sql security definer set search_path = '' as $$
  update steward.claim
     set state = 'released', released_at = due_at, invite_token_sha256 = null
   where state in ('claimed', 'in_progress') and due_at < now();
$$;

create function steward._working(state text) returns boolean
language sql immutable as $$ select state in ('claimed', 'in_progress') $$;

create function steward._is_crew(claim_id uuid, uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (
    select from steward.claim_member m
     where m.claim_id = _is_crew.claim_id and m.user_id = uid and m.left_at is null
  )
$$;

-- Anyone who is or was on the crew, places left by deleting one's data
-- included: none of them may review the claim.
create function steward._was_crew(claim_id uuid, uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select from steward.claim_member m where m.claim_id = _was_crew.claim_id and m.user_id = uid)
$$;

-- The claim, locked for the rest of the transaction, or 404.
create function steward._claim_for_update(claim_id uuid) returns steward.claim
language plpgsql security definer set search_path = '' as $$
declare
  c steward.claim;
begin
  select * into c from steward.claim where id = claim_id for update;
  if not found then
    perform steward._refuse('PT404', 'No such claim');
  end if;
  return c;
end
$$;

-- The claim, locked, if the caller is on its crew and it is in one of `states`.
create function steward._crew_claim(claim_id uuid, uid uuid, states text[] default array['claimed', 'in_progress'])
returns steward.claim
language plpgsql security definer set search_path = '' as $$
declare
  c steward.claim := steward._claim_for_update(claim_id);
begin
  if not steward._is_crew(c.id, uid) then
    perform steward._refuse('PT403', 'Only this claim''s crew can do that');
  end if;
  if not (c.state = any (states)) then
    perform steward._refuse('PT409', 'This claim is ' || replace(c.state, '_', ' ') || ', so that cannot be done now');
  end if;
  return c;
end
$$;

-- Names on a claim show to its crew, and to everyone once the work is
-- verified; before that, nobody else learns who will be out at the site.
create function steward._shows_names(c steward.claim, uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select c.state = 'verified' or (uid is not null and steward._is_crew(c.id, uid))
$$;

create function steward._display_name(uid uuid) returns text
language sql stable security definer set search_path = '' as $$
  select display_name from steward.profile where user_id = uid
$$;

create function steward._claim_summary(c steward.claim, uid uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'id', c.id,
    'rims_id', c.rims_id,
    'state', c.state,
    'claimed_at', c.claimed_at,
    'due_at', c.due_at,
    'submitted_at', c.submitted_at,
    'claimer', case when steward._shows_names(c, uid) then steward._display_name(c.claimer_id) end,
    'crew_size', (select count(*) from steward.claim_member m where m.claim_id = c.id and m.left_at is null),
    'you_are_crew', uid is not null and steward._is_crew(c.id, uid)
  )
$$;

create function steward._claim_detail(claim_id uuid, uid uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare
  c steward.claim;
  names boolean;
begin
  select * into c from steward.claim where id = claim_id;
  names := steward._shows_names(c, uid);
  return steward._claim_summary(c, uid) || jsonb_build_object(
    'started_at', c.started_at,
    'sent_back_at', c.sent_back_at,
    'verified_at', c.verified_at,
    'released_at', c.released_at,
    'steps_done', to_jsonb(c.steps_done),
    'notes', c.notes,
    'review_note', c.review_note,
    'reviewed_by', c.reviewed_by_name,
    'crew', coalesce((
      select jsonb_agg(jsonb_build_object(
               'name', case when names then p.display_name end,
               'you', m.user_id = uid,
               'hours', h.tenths / 10.0
             ) order by m.joined_at)
        from steward.claim_member m
        join steward.profile p on p.user_id = m.user_id
        left join steward.hours h on h.claim_id = m.claim_id and h.user_id = m.user_id
       where m.claim_id = c.id and m.left_at is null
    ), '[]'::jsonb),
    'photos', coalesce((
      select jsonb_agg(jsonb_build_object(
               'id', ph.id, 'phase', ph.phase, 'point', ph.point,
               'path', ph.object_name, 'created_at', ph.created_at
             ) order by ph.created_at)
        from steward.photo ph where ph.claim_id = c.id
    ), '[]'::jsonb),
    'you_may_review', uid is not null and c.state = 'submitted' and not steward._was_crew(c.id, uid)
  );
end
$$;


-- ---------------------------------------------------------------------------
-- You
-- ---------------------------------------------------------------------------

create function steward.me() returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
begin
  return jsonb_build_object('display_name', steward._display_name(uid));
end
$$;

-- Null clears it.
create function steward.set_display_name(p_name text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
begin
  update steward.profile set display_name = steward._text('Your name', p_name, 40) where user_id = uid;
  return steward.me();
end
$$;

-- Deletes what is the caller's own: their name (here and on every history
-- entry it was copied to), their lists and their hours. Claims they were
-- working on go back to Open, and they leave every crew they were on.
-- What stays, without a name: the claims and weights changes they made, which
-- are other people's history too, and their crew places, marked left, which
-- give no access but keep them from ever reviewing work they were part of.
-- Signing in again starts an empty account. The Supabase account is
-- OurHike's, and is not touched.
create function steward.delete_my_data() returns void
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
begin
  perform steward._lock(uid);
  update steward.claim
     set state = 'released', released_at = now(), invite_token_sha256 = null
   where claimer_id = uid and state in ('claimed', 'in_progress');
  update steward.claim_member set left_at = now() where user_id = uid and left_at is null;
  update steward.club_weights set changed_by_name = null where changed_by = uid;
  update steward.claim set reviewed_by_name = null where reviewed_by = uid;
  delete from steward.site_list where owner_id = uid;
  delete from steward.hours where user_id = uid;
  update steward.profile set display_name = null, deleted_at = now() where user_id = uid;
end
$$;


-- ---------------------------------------------------------------------------
-- Lists and share links. A list is its owner's alone: anyone else asking for
-- it by id gets 404, not 403, so ids cannot be probed. Sharing is a random
-- token the owner hands out; opening one needs sign-in (PLAN.md §8).
-- ---------------------------------------------------------------------------

create function steward._list_summary(l steward.site_list) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'id', l.id, 'name', l.name,
    'item_count', (select count(*) from steward.site_list_item i where i.list_id = l.id),
    'shared', l.share_token_sha256 is not null,
    'created_at', l.created_at, 'updated_at', l.updated_at
  )
$$;

create function steward._list_detail(list_id uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select steward._list_summary(l) || jsonb_build_object('rims_ids', coalesce((
           select jsonb_agg(i.rims_id order by i.seq) from steward.site_list_item i where i.list_id = l.id
         ), '[]'::jsonb))
    from steward.site_list l where l.id = list_id
$$;

create function steward._own_list(list_id uuid, uid uuid) returns steward.site_list
language plpgsql security definer set search_path = '' as $$
declare
  l steward.site_list;
begin
  select * into l from steward.site_list where id = list_id and owner_id = uid for update;
  if not found then
    perform steward._refuse('PT404', 'No such list');
  end if;
  return l;
end
$$;

create function steward._rims_id(value text) returns text
language plpgsql immutable as $$
begin
  if value is null or value !~ steward.rims_id_pattern() then
    perform steward._refuse('PT422', 'That is not a site id');
  end if;
  return value;
end
$$;

create function steward.my_lists() returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
begin
  return coalesce((
    select jsonb_agg(steward._list_summary(l) order by l.updated_at desc)
      from steward.site_list l where l.owner_id = uid
  ), '[]'::jsonb);
end
$$;

create function steward.read_list(p_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
begin
  perform steward._own_list(p_id, uid);
  return steward._list_detail(p_id);
end
$$;

create function steward.create_list(p_name text, p_rims_ids text[] default '{}') returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
  new_id uuid;
  rims text;
begin
  perform steward._lock(uid);
  if (select count(*) from steward.site_list where owner_id = uid) >= steward.lists_per_user() then
    perform steward._refuse('PT409', 'You already have ' || steward.lists_per_user() || ' lists, the most one account can keep');
  end if;
  if coalesce(cardinality(p_rims_ids), 0) > steward.items_per_list() then
    perform steward._refuse('PT422', 'A list holds at most ' || steward.items_per_list() || ' sites');
  end if;
  insert into steward.site_list (owner_id, name) values (uid, steward._text('The list''s name', p_name, 80))
  returning id into new_id;
  foreach rims in array coalesce(p_rims_ids, '{}') loop
    insert into steward.site_list_item (list_id, rims_id) values (new_id, steward._rims_id(rims))
    on conflict do nothing;
  end loop;
  return steward._list_detail(new_id);
end
$$;

create function steward.rename_list(p_id uuid, p_name text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
begin
  perform steward._own_list(p_id, uid);
  update steward.site_list set name = steward._text('The list''s name', p_name, 80), updated_at = now() where id = p_id;
  return steward._list_detail(p_id);
end
$$;

create function steward.delete_list(p_id uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
begin
  perform steward._own_list(p_id, uid);
  delete from steward.site_list where id = p_id;
end
$$;

-- Saving a site twice keeps one entry.
create function steward.add_to_list(p_id uuid, p_rims_id text) returns void
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
  rims text := steward._rims_id(p_rims_id);
begin
  perform steward._own_list(p_id, uid);
  if exists (select from steward.site_list_item where list_id = p_id and rims_id = rims) then
    return;
  end if;
  if (select count(*) from steward.site_list_item where list_id = p_id) >= steward.items_per_list() then
    perform steward._refuse('PT409', 'A list holds at most ' || steward.items_per_list() || ' sites');
  end if;
  insert into steward.site_list_item (list_id, rims_id) values (p_id, rims) on conflict do nothing;
  update steward.site_list set updated_at = now() where id = p_id;
end
$$;

create function steward.remove_from_list(p_id uuid, p_rims_id text) returns void
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
begin
  perform steward._own_list(p_id, uid);
  delete from steward.site_list_item where list_id = p_id and rims_id = p_rims_id;
  update steward.site_list set updated_at = now() where id = p_id;
end
$$;

-- A new token, replacing any earlier one: sharing again is how a leaked link
-- is stopped. Only its hash is kept.
create function steward.share_list(p_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
  token text := steward._token();
begin
  perform steward._own_list(p_id, uid);
  update steward.site_list set share_token_sha256 = steward._sha256(token) where id = p_id;
  return jsonb_build_object('token', token);
end
$$;

create function steward.unshare_list(p_id uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
begin
  perform steward._own_list(p_id, uid);
  update steward.site_list set share_token_sha256 = null where id = p_id;
end
$$;

create function steward.open_shared_list(p_token text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  l steward.site_list;
begin
  perform steward._caller();
  if p_token is null or char_length(p_token) not between 16 and 128 then
    perform steward._refuse('PT422', 'That is not a share link');
  end if;
  select * into l from steward.site_list where share_token_sha256 = steward._sha256(p_token);
  if not found then
    perform steward._refuse('PT404', 'This share link is not valid. Its owner may have replaced or stopped it.');
  end if;
  return jsonb_build_object(
    'name', l.name,
    'owner', steward._display_name(l.owner_id),
    'rims_ids', coalesce((select jsonb_agg(i.rims_id order by i.seq) from steward.site_list_item i where i.list_id = l.id), '[]'::jsonb),
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

create function steward._weights_of(w steward.club_weights) returns jsonb
language sql immutable as $$
  select jsonb_build_object('deficit', w.deficit, 'water', w.water, 'trail', w.trail,
                            'cluster', w.cluster, 'restricted', w.restricted)
$$;

create function steward._current_weights(club text) returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(
    (select steward._weights_of(w) from steward.club_weights w where w.club = _current_weights.club
      order by w.changed_at desc, w.id desc limit 1),
    steward.default_weights())
$$;

-- Anyone may read a club's weights and their history; by_you is false for
-- someone signed out.
create function steward.read_weights(p_club text) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'club', p_club,
    'current', steward._current_weights(p_club),
    'defaults', steward.default_weights(),
    'history', coalesce((
      select jsonb_agg(entry order by changed_at desc, id desc) from (
        select w.id, w.changed_at,
               steward._weights_of(w) || jsonb_build_object(
                 'id', w.id, 'note', w.note, 'restored_from', w.restored_from,
                 'changed_by', w.changed_by_name, 'by_you', w.changed_by is not distinct from auth.uid() and auth.uid() is not null,
                 'changed_at', w.changed_at) as entry
          from steward.club_weights w where w.club = p_club
         order by w.changed_at desc, w.id desc
         limit steward.weights_history_limit()) recent
    ), '[]'::jsonb)
  )
$$;

create function steward._weight(name text, value int) returns int
language plpgsql immutable as $$
begin
  if value is null or value not between 0 and 100 then
    perform steward._refuse('PT422', 'The ' || name || ' weight must be a whole number from 0 to 100');
  end if;
  return value;
end
$$;

create function steward._add_weights(uid uuid, club text, weights jsonb, note text, restored_from bigint) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  if not exists (select from steward.site s where s.club = _add_weights.club) then
    perform steward._refuse('PT422', 'No club by that name in the latest analysis');
  end if;
  if weights = steward._current_weights(club) then
    perform steward._refuse('PT422', 'These are already the club''s weights');
  end if;
  perform steward._lock(uid);
  if (select count(*) from steward.club_weights w
       where w.changed_by = uid and w.changed_at >= now() - interval '1 day') >= steward.weight_changes_per_day() then
    perform steward._refuse('PT429', 'One account can change weights ' || steward.weight_changes_per_day() || ' times a day');
  end if;
  insert into steward.club_weights (club, deficit, water, trail, cluster, restricted, note, restored_from, changed_by, changed_by_name)
  values (club, (weights ->> 'deficit')::int, (weights ->> 'water')::int, (weights ->> 'trail')::int,
          (weights ->> 'cluster')::int, (weights ->> 'restricted')::int,
          steward._text('The note', note, 200), restored_from, uid, steward._display_name(uid));
  return steward.read_weights(club);
end
$$;

create function steward.change_weights(
  p_club text, p_deficit int, p_water int, p_trail int, p_cluster int, p_restricted int, p_note text default null
) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
begin
  return steward._add_weights(uid, steward._text('The club', p_club, 120), jsonb_build_object(
    'deficit', steward._weight('deficit', p_deficit), 'water', steward._weight('water', p_water),
    'trail', steward._weight('trail', p_trail), 'cluster', steward._weight('cluster', p_cluster),
    'restricted', steward._weight('restricted', p_restricted)), p_note, null);
end
$$;

-- Undo: a new entry with an earlier entry's weights, pointing back at it.
create function steward.restore_weights(p_entry_id bigint, p_note text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
  earlier steward.club_weights;
begin
  select * into earlier from steward.club_weights where id = p_entry_id;
  if not found then
    perform steward._refuse('PT404', 'No such weights entry');
  end if;
  return steward._add_weights(uid, earlier.club, steward._weights_of(earlier), p_note, earlier.id);
end
$$;


-- ---------------------------------------------------------------------------
-- Claims (PLAN.md §6, #1910):
--
--   claimed ──first before photo──► in_progress ──submit──► submitted ──verify──► verified
--      │                                │                       ├──send back──► in_progress
--      └──── release, or due_at passes ─┴──► released ◄──reject──┘
--
-- The clock is due_at. It stops at submitted, so a slow reviewer never costs
-- a crew its claim. A send-back gives back what the crew had left, at least
-- send_back_days(); the after photos must then be retaken. A reject releases
-- the site, and the rejecter may not claim it for rejecter_wait_days().
-- ---------------------------------------------------------------------------

-- One site, or several at once (a site and its cluster). All or none.
create function steward.claim_sites(p_rims_ids text[]) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
  sites text[];
  refused text;
  held int;
  made jsonb := '[]'::jsonb;
  c steward.claim;
  rims text;
begin
  if coalesce(cardinality(p_rims_ids), 0) not between 1 and steward.sites_per_claim_request() then
    perform steward._refuse('PT422', 'Claim between 1 and ' || steward.sites_per_claim_request() || ' sites at once');
  end if;
  select array_agg(r order by first_seen) into sites from (
    select steward._rims_id(r) as r, min(n) as first_seen from unnest(p_rims_ids) with ordinality as t(r, n) group by r
  ) distinct_sites;
  select string_agg(r, ', ') into refused from unnest(sites) r
   where not exists (select from steward.site s where s.rims_id = r and s.workable);
  if refused is not null then
    perform steward._refuse('PT422', 'Not a site the latest analysis says needs work: ' || refused);
  end if;
  perform steward._release_overdue();
  perform steward._lock(uid);
  select string_agg(distinct cl.rims_id, ', ' order by cl.rims_id) into refused from steward.claim cl
   where cl.rims_id = any (sites) and cl.rejected_by = uid
     and cl.released_at > now() - make_interval(days => steward.rejecter_wait_days());
  if refused is not null then
    perform steward._refuse('PT409', 'You rejected the last claim on ' || refused || ', so someone else gets the next '
      || steward.rejecter_wait_days() || ' days to claim it');
  end if;
  -- A place left by deleting one's data still counts on a claim this account
  -- made: its submitted claims hold their sites until reviewed (the fourth
  -- pass's B). Other crews' claims it left do not count.
  select count(*) into held from steward.claim cl join steward.claim_member m on m.claim_id = cl.id
   where m.user_id = uid and (m.left_at is null or cl.claimer_id = uid)
     and cl.state in ('claimed', 'in_progress', 'submitted');
  if held + cardinality(sites) > steward.live_claims_per_user() then
    perform steward._refuse('PT409', 'One account holds at most ' || steward.live_claims_per_user()
      || ' sites at a time, counting ones waiting for review');
  end if;
  select string_agg(cl.rims_id, ', ' order by cl.rims_id) into refused from steward.claim cl
   where cl.rims_id = any (sites) and cl.state in ('claimed', 'in_progress', 'submitted');
  if refused is not null then
    perform steward._refuse('PT409', 'Already claimed: ' || refused);
  end if;
  begin
    foreach rims in array sites loop
      insert into steward.claim (rims_id, claimer_id, state, due_at)
      values (rims, uid, 'claimed', now() + make_interval(days => steward.claim_days()))
      returning * into c;
      insert into steward.claim_member (claim_id, user_id) values (c.id, uid);
      made := made || jsonb_build_array(steward._claim_summary(c, uid));
    end loop;
  exception when unique_violation then
    -- Someone else claimed one of them between the check and the insert.
    perform steward._refuse('PT409', 'Someone claimed one of these sites a moment ago');
  end;
  return made;
end
$$;

-- The claim holding a site now, or null when it is open.
create function steward.claim_for_site(p_rims_id text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
  c steward.claim;
begin
  perform steward._release_overdue();
  select * into c from steward.claim
   where rims_id = steward._rims_id(p_rims_id) and state in ('claimed', 'in_progress', 'submitted');
  if not found then
    return null;
  end if;
  return steward._claim_summary(c, uid);
end
$$;

create function steward.my_claims() returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
begin
  perform steward._release_overdue();
  return coalesce((
    select jsonb_agg(summary order by claimed_at desc) from (
      select steward._claim_summary(cl, uid) as summary, cl.claimed_at
        from steward.claim cl join steward.claim_member m on m.claim_id = cl.id
       where m.user_id = uid and m.left_at is null
       order by cl.claimed_at desc limit 100) mine
  ), '[]'::jsonb);
end
$$;

create function steward.read_claim(p_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
begin
  perform steward._release_overdue();
  if not exists (select from steward.claim where id = p_id) then
    perform steward._refuse('PT404', 'No such claim');
  end if;
  return steward._claim_detail(p_id, uid);
end
$$;

create function steward.release_claim(p_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
  c steward.claim;
begin
  perform steward._release_overdue();
  c := steward._crew_claim(p_id, uid);
  if c.claimer_id is distinct from uid then
    perform steward._refuse('PT403', 'Only the person who claimed the site can release it');
  end if;
  update steward.claim set state = 'released', released_at = now(), invite_token_sha256 = null where id = p_id;
  return steward._claim_detail(p_id, uid);
end
$$;

-- A crew invite link, replacing any earlier one.
create function steward.make_invite(p_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
  token text := steward._token();
begin
  perform steward._release_overdue();
  perform steward._crew_claim(p_id, uid);
  update steward.claim set invite_token_sha256 = steward._sha256(token) where id = p_id;
  return jsonb_build_object('token', token);
end
$$;

create function steward.join_claim(p_token text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
  c steward.claim;
  place steward.claim_member;
begin
  perform steward._release_overdue();
  if p_token is null or char_length(p_token) not between 16 and 128 then
    perform steward._refuse('PT422', 'That is not an invite link');
  end if;
  select * into c from steward.claim where invite_token_sha256 = steward._sha256(p_token) for update;
  if not found or not steward._working(c.state) then
    perform steward._refuse('PT404', 'This invite is not valid any more. Ask the crew for a new one.');
  end if;
  if not steward._is_crew(c.id, uid) then
    if (select count(*) from steward.claim_member m where m.claim_id = c.id and m.left_at is null) >= steward.crew_max() then
      perform steward._refuse('PT409', 'This crew is full at ' || steward.crew_max());
    end if;
    select * into place from steward.claim_member m where m.claim_id = c.id and m.user_id = uid;
    if found then
      -- Someone who deleted their data and was invited back.
      update steward.claim_member m set left_at = null where m.claim_id = c.id and m.user_id = uid;
    else
      insert into steward.claim_member (claim_id, user_id) values (c.id, uid);
    end if;
  end if;
  return steward._claim_summary(c, uid);
end
$$;


-- ---------------------------------------------------------------------------
-- Photos. The phone uploads the JPEG to the steward-photos bucket first, at
-- `<claim id>/<its id for the photo>.jpg` (the bucket's insert policy, below,
-- lets only the claim's crew do that while the claim is open), then calls
-- add_photo() to put it on the claim.
--
-- The phone redraws every photo before it leaves, which strips the location
-- a camera writes into it (web/src/photo.ts). With no server in between,
-- nothing redraws it again: the old API did, against a phone that had been
-- tampered with (the review's finding 6). What remains is the bucket's own
-- type and size limits, set below.
-- ---------------------------------------------------------------------------

-- The bucket's insert policy asks this.
create function steward.may_upload_photo(object_name text) returns boolean
language plpgsql stable security definer set search_path = '' as $$
declare
  uid uuid := auth.uid();
  claim_id uuid;
begin
  if uid is null or coalesce((auth.jwt() ->> 'is_anonymous')::boolean, false)
     or object_name is null or object_name !~ steward.photo_object_pattern() then
    return false;
  end if;
  claim_id := split_part(object_name, '/', 1)::uuid;
  return exists (
           select from steward.claim c
            where c.id = claim_id and steward._working(c.state) and c.due_at >= now()
              and steward._is_crew(c.id, uid))
     and (select count(*) from storage.objects o
           where o.bucket_id = 'steward-photos' and o.name like claim_id::text || '/%') < steward.objects_per_claim();
end
$$;

-- The bucket's delete policy asks this: the crew of an open claim may delete
-- an object no photo on the claim points at (one replaced or removed).
create function steward.may_delete_photo_object(object_name text) returns boolean
language plpgsql stable security definer set search_path = '' as $$
declare
  uid uuid := auth.uid();
  claim_id uuid;
begin
  if uid is null or object_name is null or object_name !~ steward.photo_object_pattern() then
    return false;
  end if;
  claim_id := split_part(object_name, '/', 1)::uuid;
  return exists (
           select from steward.claim c
            where c.id = claim_id and steward._working(c.state) and steward._is_crew(c.id, uid))
     and not exists (select from steward.photo p where p.object_name = may_delete_photo_object.object_name);
end
$$;

-- This crew member's phone already delivered this photo. Asked before the
-- claim's state: a photo that arrived before the claim was submitted is still
-- there afterwards, and the phone should hear that, not a refusal.
create function steward._sent_before(claim_id uuid, uid uuid, client_id text) returns boolean
language sql stable security definer set search_path = '' as $$
  select client_id is not null and steward._is_crew(claim_id, uid)
     and exists (select from steward.photo_receipt r where r.claim_id = _sent_before.claim_id and r.client_id = _sent_before.client_id)
$$;

-- `p_replaces`, for a before or after photo the phone queued with no signal:
-- the id of the photo in its slot when it was taken, or 'nothing'. If the
-- slot holds anything else now, the photo is refused with PT412 rather than
-- put over the newer one; the phone keeps it. Phones' clocks are not trusted
-- to say which photo is newer.
create function steward.add_photo(
  p_claim_id uuid, p_phase text, p_point int, p_client_id text, p_replaces text default null
) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
  c steward.claim;
  object_path text;
  current_id uuid;
  replaced text;
begin
  if p_phase is null or p_phase not in ('before', 'after', 'extra')
     or (p_phase = 'extra') <> (p_point is null) or (p_point is not null and p_point not in (1, 2)) then
    perform steward._refuse('PT422', 'A before or after photo needs photo point 1 or 2; an extra needs none');
  end if;
  if p_client_id is null or p_client_id !~ steward.client_id_pattern() then
    perform steward._refuse('PT422', 'That is not a photo id');
  end if;
  if p_replaces is not null and p_replaces !~ '^(nothing|[0-9a-f-]{36})$' then
    perform steward._refuse('PT422', 'That is not a photo id');
  end if;
  perform steward._release_overdue();
  c := steward._claim_for_update(p_claim_id);
  if steward._sent_before(c.id, uid, p_client_id) then
    return steward._claim_detail(c.id, uid);
  end if;
  c := steward._crew_claim(p_claim_id, uid);
  object_path := c.id::text || '/' || p_client_id || '.jpg';
  if not exists (select from storage.objects o where o.bucket_id = 'steward-photos' and o.name = object_path) then
    perform steward._refuse('PT422', 'The photo has not arrived. Send it again.');
  end if;
  if (select count(*) from steward.photo p where p.claim_id = c.id) >= steward.photos_per_claim() then
    perform steward._refuse('PT409', 'A claim holds at most ' || steward.photos_per_claim() || ' photos');
  end if;
  if p_point is not null then
    select p.id, p.object_name into current_id, replaced
      from steward.photo p where p.claim_id = c.id and p.phase = p_phase and p.point = p_point;
    if p_replaces is not null and p_replaces <> coalesce(current_id::text, 'nothing') then
      perform steward._refuse('PT412',
        'This point has a newer photo than this phone had seen when it took this one, so it was not put over it');
    end if;
    delete from steward.photo p where p.claim_id = c.id and p.phase = p_phase and p.point = p_point;
  end if;
  insert into steward.photo (claim_id, phase, point, object_name, uploaded_by) values (c.id, p_phase, p_point, object_path, uid);
  insert into steward.photo_receipt (claim_id, client_id) values (c.id, p_client_id);
  if p_phase = 'before' and c.state = 'claimed' then
    update steward.claim set state = 'in_progress', started_at = now() where id = c.id;
  end if;
  -- The object the new photo replaced, which no photo uses now: the app
  -- deletes it, so a retake (someone was in the frame) does not stay public.
  return steward._claim_detail(c.id, uid) || jsonb_build_object('unused_path', replaced);
end
$$;

-- The photo comes off the claim, and the answer names its object, which
-- may_delete_photo_object() now lets the crew delete and the app does.
create function steward.remove_photo(p_claim_id uuid, p_photo_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
  removed text;
begin
  perform steward._release_overdue();
  perform steward._crew_claim(p_claim_id, uid);
  delete from steward.photo where id = p_photo_id and claim_id = p_claim_id returning object_name into removed;
  if removed is null then
    perform steward._refuse('PT404', 'No such photo on this claim');
  end if;
  return steward._claim_detail(p_claim_id, uid) || jsonb_build_object('unused_path', removed);
end
$$;


-- ---------------------------------------------------------------------------
-- Hours, submitting, reviewing
-- ---------------------------------------------------------------------------

-- Your own hours on this claim, across all your visits, in half hours.
create function steward.log_hours(p_claim_id uuid, p_hours numeric) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
begin
  if p_hours is null or p_hours <= 0 or p_hours > steward.hours_max() or (p_hours * 2) <> trunc(p_hours * 2) then
    perform steward._refuse('PT422', 'Hours are in half hours, from 0.5 to ' || steward.hours_max());
  end if;
  perform steward._release_overdue();
  perform steward._crew_claim(p_claim_id, uid);
  insert into steward.hours (claim_id, user_id, tenths) values (p_claim_id, uid, (p_hours * 10)::int)
  on conflict (claim_id, user_id) do update set tenths = excluded.tenths;
  return steward._claim_detail(p_claim_id, uid);
end
$$;

-- Each photo point needs a before and an after. After a send-back, only after
-- photos taken since count: resubmitting the same pictures is not a fix.
create function steward._missing_photos(c steward.claim) returns text
language sql stable security definer set search_path = '' as $$
  select string_agg(phase || ' at point ' || point
                    || case when phase = 'after' and c.sent_back_at is not null then ' (retaken since it was sent back)' else '' end,
                    ', ' order by point, phase desc)
    from (values ('before', 1), ('after', 1), ('before', 2), ('after', 2)) need(phase, point)
   where not exists (
     select from steward.photo p
      where p.claim_id = c.id and p.phase = need.phase and p.point = need.point
        and not (p.phase = 'after' and c.sent_back_at is not null and p.created_at <= c.sent_back_at))
$$;

create function steward.submit_claim(p_id uuid, p_steps_done text[] default '{}', p_notes text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
  c steward.claim;
  missing text;
  steps text[] := '{}';
  step text;
begin
  if coalesce(cardinality(p_steps_done), 0) > 20 then
    perform steward._refuse('PT422', 'At most 20 steps');
  end if;
  foreach step in array coalesce(p_steps_done, '{}') loop
    step := steward._text('A step', step, 120);
    if not (step = any (steps)) then
      steps := steps || step;
    end if;
  end loop;
  perform steward._release_overdue();
  c := steward._crew_claim(p_id, uid, array['in_progress']);
  missing := steward._missing_photos(c);
  if missing is not null then
    perform steward._refuse('PT422', 'Still needed before submitting: ' || missing);
  end if;
  update steward.claim
     set steps_done = steps, notes = steward._text('The notes', p_notes, 1000, true),
         state = 'submitted', submitted_at = now(), invite_token_sha256 = null
   where id = p_id;
  return steward._claim_detail(p_id, uid);
end
$$;

-- Submitted claims this caller may review: oldest first, none of their own crew's.
create function steward.reviews() returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
begin
  perform steward._release_overdue();
  return coalesce((
    select jsonb_agg(summary order by submitted_at) from (
      select steward._claim_summary(c, uid) as summary, c.submitted_at
        from steward.claim c
       where c.state = 'submitted' and not steward._was_crew(c.id, uid)
       order by c.submitted_at limit 50) waiting
  ), '[]'::jsonb);
end
$$;

-- Never by anyone who is or was on the crew.
--   verify: confirms the crew's hours;
--   send_back: needs a note; the crew gets back the time it had left when it
--     submitted, and at least send_back_days(), so one reviewer cannot shorten
--     a crew's clock (the review's finding 9); the after photos are retaken;
--   reject: needs a note; the site is released, the hours are not counted,
--     and the reviewer may not claim it for rejecter_wait_days().
create function steward.review_claim(p_id uuid, p_verdict text, p_note text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
  c steward.claim;
  note text := steward._text('The note', p_note, 500, true);
begin
  if p_verdict is null or p_verdict not in ('verify', 'send_back', 'reject') then
    perform steward._refuse('PT422', 'A review is verify, send_back or reject');
  end if;
  c := steward._claim_for_update(p_id);
  if steward._was_crew(c.id, uid) then
    perform steward._refuse('PT403', 'Someone off the crew has to review this');
  end if;
  if c.state <> 'submitted' then
    perform steward._refuse('PT409', 'Only a submitted claim can be reviewed');
  end if;
  if p_verdict <> 'verify' and note is null then
    perform steward._refuse('PT422', 'Say what is missing when sending back or rejecting');
  end if;
  update steward.claim
     set reviewed_by = uid, reviewed_by_name = steward._display_name(uid), review_note = note
   where id = c.id;
  if p_verdict = 'verify' then
    update steward.claim set state = 'verified', verified_at = now() where id = c.id;
    update steward.hours set verified = true where claim_id = c.id;
  elsif p_verdict = 'send_back' then
    update steward.claim
       set state = 'in_progress', sent_back_at = now(), submitted_at = null,
           due_at = now() + greatest(c.due_at - coalesce(c.submitted_at, now()), make_interval(days => steward.send_back_days()))
     where id = c.id;
  else
    update steward.claim
       set state = 'released', released_at = now(), rejected_by = uid, invite_token_sha256 = null
     where id = c.id;
  end if;
  return steward._claim_detail(c.id, uid);
end
$$;

create function steward.my_hours() returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := steward._caller();
begin
  return (
    select jsonb_build_object(
      'verified', coalesce(sum(tenths) filter (where verified), 0) / 10.0,
      'waiting', coalesce(sum(tenths) filter (where not verified), 0) / 10.0,
      'claims', count(*))
      from steward.hours where user_id = uid
  );
end
$$;


-- ---------------------------------------------------------------------------
-- What is open: anyone may read these, through Supabase's REST API with the
-- public key, or as the files the analysis job publishes beside sites.json.
-- They read the tables as their owner, so they are the whole of what an
-- anonymous reader sees. Names appear only on verified work.
-- ---------------------------------------------------------------------------

create view steward.open_claims as
select c.id,
       c.rims_id,
       case when c.state in ('claimed', 'in_progress') and c.due_at < now() then 'released' else c.state end as state,
       c.claimed_at,
       case when c.state in ('claimed', 'in_progress', 'submitted') then c.due_at end as due_at,
       c.submitted_at,
       c.verified_at,
       coalesce(c.released_at, case when c.state in ('claimed', 'in_progress') and c.due_at < now() then c.due_at end) as released_at,
       (select count(*) from steward.claim_member m where m.claim_id = c.id and m.left_at is null) as crew_size,
       case when c.state = 'verified' then (select p.display_name from steward.profile p where p.user_id = c.claimer_id) end as claimer,
       case when c.state = 'verified' then c.reviewed_by_name end as verified_by,
       case when c.state = 'verified' then c.steps_done end as steps_done,
       case when c.state = 'verified' then (select sum(h.tenths) / 10.0 from steward.hours h where h.claim_id = c.id and h.verified) end as verified_hours
  from steward.claim c;

-- The before and after photos of verified work.
create view steward.open_photos as
select p.claim_id, c.rims_id, p.phase, p.point, p.object_name as path, p.created_at
  from steward.photo p join steward.claim c on c.id = p.claim_id
 where c.state = 'verified';

create view steward.open_weights as
select w.id, w.club, w.deficit, w.water, w.trail, w.cluster, w.restricted, w.note, w.restored_from,
       w.changed_by_name as changed_by, w.changed_at
  from steward.club_weights w;


-- ---------------------------------------------------------------------------
-- The analysis job's load: the latest sites, replacing the last load.
-- ---------------------------------------------------------------------------

-- `p_sites` is sites.json's records; a site is workable when its action is
-- one a volunteer claims (close_restore or harden), as the old API read it.
-- Refuses a load with fewer than half the sites held now: a truncated or
-- broken file would otherwise empty the list every claim is checked against.
-- `@unvalidated`, the half: ATC's inventory changed by a handful of sites a
-- week while this was built, and nothing has measured a real week.
create function steward.load_sites(p_sites jsonb) returns int
language plpgsql security definer set search_path = '' as $$
declare
  incoming int;
  held int;
begin
  if jsonb_typeof(p_sites) is distinct from 'array' then
    raise exception 'sites.json is not a list of sites';
  end if;
  select count(distinct r ->> 'rims_id') into incoming
    from jsonb_array_elements(p_sites) r
   where jsonb_typeof(r) = 'object' and (r ->> 'rims_id') ~ steward.rims_id_pattern();
  select count(*) into held from steward.site;
  if incoming = 0 or incoming < held / 2 then
    raise exception 'sites.json names % sites where % are loaded; refusing to replace them', incoming, held;
  end if;
  with arriving as (
    select distinct on (r ->> 'rims_id')
           r ->> 'rims_id' as rims_id,
           nullif(r ->> 'club', '') as club,
           coalesce(r ->> 'action', '') in ('close_restore', 'harden') as workable
      from jsonb_array_elements(p_sites) r
     where jsonb_typeof(r) = 'object' and (r ->> 'rims_id') ~ steward.rims_id_pattern()
  ), kept as (
    insert into steward.site (rims_id, club, workable, loaded_at)
    select rims_id, club, workable, now() from arriving
    on conflict (rims_id) do update set club = excluded.club, workable = excluded.workable, loaded_at = excluded.loaded_at
    returning rims_id
  )
  delete from steward.site s where not exists (select from arriving a where a.rims_id = s.rims_id);
  return incoming;
end
$$;


-- ---------------------------------------------------------------------------
-- Photos bucket
-- ---------------------------------------------------------------------------

-- Public, so a photo's address works for anyone; only JPEGs, at most 3 MB,
-- which is what the app sends (2048 px on the long side at quality 0.85 is
-- typically under 1 MB). The Storage service enforces both, not Postgres.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('steward-photos', 'steward-photos', true, 3145728, array['image/jpeg'])
on conflict (id) do update
  set public = excluded.public, file_size_limit = excluded.file_size_limit, allowed_mime_types = excluded.allowed_mime_types;

create policy "steward: crews upload their claim's photos"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'steward-photos' and steward.may_upload_photo(name));

-- Deleting asks Storage to read the row first, so the crew needs to see it.
create policy "steward: crews see their open claims' objects"
  on storage.objects for select to authenticated
  using (bucket_id = 'steward-photos' and steward.may_delete_photo_object(name));

create policy "steward: crews delete objects no photo uses"
  on storage.objects for delete to authenticated
  using (bucket_id = 'steward-photos' and steward.may_delete_photo_object(name));
-- No update policy: an uploaded object is never overwritten.


-- ---------------------------------------------------------------------------
-- Grants. Everything else stays revoked: explicitly, in case a project's
-- default privileges reach this schema as Supabase's reach `public`.
-- ---------------------------------------------------------------------------

revoke all on all tables in schema steward from public, anon, authenticated;
revoke all on all sequences in schema steward from public, anon, authenticated;
revoke all on all functions in schema steward from public, anon, authenticated;

grant select on steward.open_claims, steward.open_photos, steward.open_weights to anon, authenticated;
grant execute on function steward.read_weights(text) to anon, authenticated;
grant execute on function steward.may_upload_photo(text), steward.may_delete_photo_object(text) to authenticated;
grant execute on function
  steward.me(), steward.set_display_name(text), steward.delete_my_data(),
  steward.my_lists(), steward.read_list(uuid), steward.create_list(text, text[]), steward.rename_list(uuid, text),
  steward.delete_list(uuid), steward.add_to_list(uuid, text), steward.remove_from_list(uuid, text),
  steward.share_list(uuid), steward.unshare_list(uuid), steward.open_shared_list(text),
  steward.change_weights(text, int, int, int, int, int, text), steward.restore_weights(bigint, text),
  steward.claim_sites(text[]), steward.claim_for_site(text), steward.my_claims(), steward.read_claim(uuid),
  steward.release_claim(uuid), steward.make_invite(uuid), steward.join_claim(text),
  steward.add_photo(uuid, text, int, text, text), steward.remove_photo(uuid, uuid),
  steward.log_hours(uuid, numeric), steward.submit_claim(uuid, text[], text), steward.reviews(),
  steward.review_claim(uuid, text, text), steward.my_hours()
  to authenticated;
grant execute on function steward.load_sites(jsonb) to steward_loader;
