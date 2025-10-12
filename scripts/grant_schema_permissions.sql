-- Grant Schema DDL Permissions for Auto-Migration
-- hh_app user needs these permissions for hh-embed-svc auto-migration

\c headhunter

-- Grant CREATE permission on search schema (for auto-migration)
GRANT CREATE ON SCHEMA search TO hh_app;

-- Grant all table permissions in search schema
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA search TO hh_app;

-- Grant sequence permissions (for auto-generated IDs)
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA search TO hh_app;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA search
  GRANT ALL PRIVILEGES ON TABLES TO hh_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA search
  GRANT ALL PRIVILEGES ON SEQUENCES TO hh_app;

-- Grant USAGE on search schema (required for access)
GRANT USAGE ON SCHEMA search TO hh_app;

-- Verify permissions
SELECT
    schemaname,
    tablename,
    tableowner,
    has_table_privilege('hh_app', schemaname || '.' || tablename, 'SELECT') as can_select,
    has_table_privilege('hh_app', schemaname || '.' || tablename, 'INSERT') as can_insert,
    has_table_privilege('hh_app', schemaname || '.' || tablename, 'UPDATE') as can_update,
    has_table_privilege('hh_app', schemaname || '.' || tablename, 'DELETE') as can_delete
FROM pg_tables
WHERE schemaname = 'search'
ORDER BY tablename;

-- Verify schema permissions
SELECT
    nspname as schema_name,
    has_schema_privilege('hh_app', nspname, 'USAGE') as can_use,
    has_schema_privilege('hh_app', nspname, 'CREATE') as can_create
FROM pg_namespace
WHERE nspname = 'search';
