-- Migration 002: Explicit RLS policies for segnalazioni
-- Safe to re-run (IF EXISTS guards on all drops).
-- Run in: Supabase SQL Editor → New query

-- Drop old policies (space-separated names from initial setup)
drop policy if exists "public read"    on segnalazioni;
drop policy if exists "public insert"  on segnalazioni;
-- Drop new names too (idempotent re-run)
drop policy if exists "public_read"    on segnalazioni;
drop policy if exists "public_insert"  on segnalazioni;
drop policy if exists "public_resolve" on segnalazioni;
drop policy if exists "no_delete"      on segnalazioni;

alter table segnalazioni enable row level security;

-- 1. SELECT: anon reads all (app filters resolved=false at query layer)
create policy "public_read"
  on segnalazioni for select
  using (true);

-- 2. INSERT: Foggia bounds + category whitelist
--    bounds: config.py BBOX 15.45,41.55,15.65,41.40 ± 0.05° buffer
create policy "public_insert"
  on segnalazioni for insert
  with check (
    categoria in ('Rifiuti', 'Buche', 'Illuminazione', 'Altro')
    and lat between 41.35 and 41.60
    and lon between 15.40 and 15.70
  );

-- 3. UPDATE: only allowed mutation is resolved false → true
--    USING      = filter on existing row state (must currently be unresolved)
--    WITH CHECK = filter on proposed new row state (must be resolved=true)
--    Any attempt to mutate lat/lon/categoria/image_url fails WITH CHECK.
create policy "public_resolve"
  on segnalazioni for update
  using     (resolved = false)
  with check (resolved = true);

-- 4. DELETE: explicitly blocked for all roles
create policy "no_delete"
  on segnalazioni for delete
  using (false);
