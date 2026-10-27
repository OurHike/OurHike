-- Stand-ins for the parts of a Supabase project that migrations/0001_steward.sql
-- uses, so its tests run on plain Postgres. Tests only: a Supabase project has
-- the real ones.
--
-- auth.uid() and auth.jwt() are Supabase's own definitions (its auth schema
-- reads the request's JWT claims from these settings, which is how PostgREST
-- and Storage hand them over). storage.buckets and storage.objects carry only
-- the columns the steward migration and its policies read, with Supabase's
-- grants on them: every role may try, and row-level security decides.

create schema if not exists auth;

create table if not exists auth.users (
  id uuid primary key,
  email text,
  is_anonymous boolean not null default false
);

create or replace function auth.jwt() returns jsonb language sql stable as $$
  select coalesce(
    nullif(current_setting('request.jwt.claim', true), ''),
    nullif(current_setting('request.jwt.claims', true), '')
  )::jsonb
$$;

create or replace function auth.uid() returns uuid language sql stable as $$
  select coalesce(
    nullif(current_setting('request.jwt.claim.sub', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
  )::uuid
$$;

grant usage on schema auth to anon, authenticated;
grant execute on function auth.uid(), auth.jwt() to anon, authenticated;

create schema if not exists storage;

create table if not exists storage.buckets (
  id text primary key,
  name text not null,
  owner uuid,
  public boolean default false,
  file_size_limit bigint,
  allowed_mime_types text[],
  created_at timestamptz default now()
);

create table if not exists storage.objects (
  id uuid primary key default gen_random_uuid(),
  bucket_id text references storage.buckets (id),
  name text,
  owner uuid,
  owner_id text,
  created_at timestamptz default now(),
  metadata jsonb,
  unique (bucket_id, name)
);

alter table storage.objects enable row level security;

grant usage on schema storage to anon, authenticated;
grant select, insert, update, delete on storage.objects to anon, authenticated;
grant select on storage.buckets to anon, authenticated;
