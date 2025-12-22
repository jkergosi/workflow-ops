-- Environment Types: system-configurable list + ordering for environments.n8n_type

create table if not exists public.environment_types (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null,
  key text not null,
  label text not null,
  sort_order integer not null default 0,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists environment_types_tenant_key_unique
  on public.environment_types (tenant_id, key);

create index if not exists environment_types_tenant_sort_idx
  on public.environment_types (tenant_id, sort_order);

-- Optional: updated_at trigger (if your project already uses a standard trigger, prefer that)
-- create or replace function public.set_updated_at() returns trigger as $$
-- begin
--   new.updated_at = now();
--   return new;
-- end;
-- $$ language plpgsql;
--
-- drop trigger if exists trg_environment_types_updated_at on public.environment_types;
-- create trigger trg_environment_types_updated_at
-- before update on public.environment_types
-- for each row execute function public.set_updated_at();

