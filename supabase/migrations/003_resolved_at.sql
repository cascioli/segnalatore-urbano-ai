-- Migration 003: Add resolved_at audit timestamp
-- Run in: Supabase SQL Editor → New query

alter table segnalazioni
  add column if not exists resolved_at timestamptz;
