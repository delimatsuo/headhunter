const Redis = require('ioredis');

const config = {
    host: process.env.REDIS_HOST || '10.99.187.236',
    port: parseInt(process.env.REDIS_PORT || '6379'),
    password: process.env.REDIS_PASSWORD,
    tls: process.env.REDIS_TLS === 'true' ? {} : undefined
};

console.log('Configuration:', JSON.stringify(config, null, 2));

const client = new Redis({
    host: config.host,
    port: config.port,
    password: config.password,
    tls: config.tls,
    connectTimeout: 5000,
    maxRetriesPerRequest: 1
});

client.on('connect', () => console.log('Connected to Redis'));
client.on('ready', () => console.log('Redis client ready'));
client.on('error', (err) => console.error('Redis error:', err));
client.on('close', () => console.log('Redis connection closed'));
client.on('reconnecting', () => console.log('Redis reconnecting'));

async function test() {
    try {
        console.log('Pinging Redis...');
        const result = await client.ping();
        console.log('Ping result:', result);

        console.log('Setting key...');
        await client.set('debug-test', 'hello');
        console.log('Key set');

        console.log('Getting key...');
        const value = await client.get('debug-test');
        console.log('Value:', value);

        process.exit(0);
    } catch (error) {
        console.error('Test failed:', error);
        process.exit(1);
    }
}

test();
