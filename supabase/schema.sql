-- Run this once in Supabase: Dashboard > SQL Editor > New query > paste > Run
create extension if not exists "pgcrypto";

-- One row per saved trip. `payload` keeps the full itinerary so a trip reloads exactly as saved.
create table if not exists public.trips (
  id            uuid primary key default gen_random_uuid(),
  client_id     text not null,                 -- anonymous browser id (no login needed)
  name          text not null,
  destination   text not null,
  country       text,
  currency      text,
  num_days      int  not null check (num_days between 1 and 10),
  budget_level  text,
  party         text,
  pace          text,
  start_date    date,
  payload       jsonb not null,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index if not exists trips_client_idx on public.trips (client_id, updated_at desc);

-- Relational breakdown: trips 1-N trip_days 1-N activities
create table if not exists public.trip_days (
  id          uuid primary key default gen_random_uuid(),
  trip_id     uuid not null references public.trips(id) on delete cascade,
  day_number  int  not null,
  day_date    date,
  theme       text,
  unique (trip_id, day_number)
);

create table if not exists public.activities (
  id            uuid primary key default gen_random_uuid(),
  trip_day_id   uuid not null references public.trip_days(id) on delete cascade,
  slot          text not null,
  position      int  not null default 0,
  name          text not null,
  area          text,
  lat           double precision,
  lon           double precision,
  description   text,
  cost_local    numeric(12,2) default 0,
  duration_hrs  numeric(5,2),
  tags          text[]
);
create index if not exists activities_day_idx on public.activities (trip_day_id);

-- Lock the tables: the backend uses the service_role key (bypasses RLS);
-- with RLS on and no policies, the public anon key cannot read or write anything.
alter table public.trips      enable row level security;
alter table public.trip_days  enable row level security;
alter table public.activities enable row level security;
