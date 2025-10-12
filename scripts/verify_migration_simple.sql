-- Simple verification query
SELECT 'search' as schema_name, count(*) as table_count FROM information_schema.tables WHERE table_schema = 'search'
UNION ALL
SELECT 'taxonomy', count(*) FROM information_schema.tables WHERE table_schema = 'taxonomy'
UNION ALL
SELECT 'msgs', count(*) FROM information_schema.tables WHERE table_schema = 'msgs'
UNION ALL
SELECT 'ops', count(*) FROM information_schema.tables WHERE table_schema = 'ops';
