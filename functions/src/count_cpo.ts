
import * as dotenv from 'dotenv';
import { Pool } from 'pg';

dotenv.config();

async function countCPO() {
    const pool = new Pool({
        host: process.env.PGVECTOR_HOST || 'localhost',
        port: parseInt(process.env.PGVECTOR_PORT || '5432'),
        database: process.env.PGVECTOR_DATABASE || 'headhunter',
        user: process.env.PGVECTOR_USER || 'postgres',
        password: process.env.PGVECTOR_PASSWORD || '',
        ssl: process.env.PGVECTOR_SSL_MODE === 'require',
    });

    try {
        console.log('Connecting to database...');
        const client = await pool.connect();
        console.log('Connected.');

        // Query 1: Count exact "Chief Product Officer" in metadata
        console.log('Querying for "Chief Product Officer"...');
        const res1 = await client.query(`
      SELECT COUNT(*) as count 
      FROM candidate_embeddings 
      WHERE metadata->>'current_title' ILIKE '%Chief Product Officer%'
      OR metadata->>'job_title' ILIKE '%Chief Product Officer%'
    `);
        console.log(`Exact "Chief Product Officer" count: ${res1.rows[0].count}`);

        // Query 2: Count "CPO"
        console.log('Querying for "CPO"...');
        const res2 = await client.query(`
      SELECT COUNT(*) as count 
      FROM candidate_embeddings 
      WHERE metadata->>'current_title' ILIKE '%CPO%'
      OR metadata->>'job_title' ILIKE '%CPO%'
    `);
        console.log(`"CPO" count: ${res2.rows[0].count}`);

        // Query 3: Count "Head of Product"
        console.log('Querying for "Head of Product"...');
        const res3 = await client.query(`
      SELECT COUNT(*) as count 
      FROM candidate_embeddings 
      WHERE metadata->>'current_title' ILIKE '%Head of Product%'
      OR metadata->>'job_title' ILIKE '%Head of Product%'
    `);
        console.log(`"Head of Product" count: ${res3.rows[0].count}`);

        // Query 4: List top 10 Product titles
        console.log('Listing top 10 Product titles...');
        const res4 = await client.query(`
      SELECT metadata->>'current_title' as title, COUNT(*) as count
      FROM candidate_embeddings
      WHERE metadata->>'current_title' ILIKE '%Product%'
      GROUP BY title
      ORDER BY count DESC
      LIMIT 10
    `);
        console.log('Top Product Titles:');
        res4.rows.forEach(r => console.log(`- ${r.title}: ${r.count}`));

        client.release();
    } catch (err) {
        console.error('Error executing query:', err);
    } finally {
        await pool.end();
    }
}

countCPO();
