import axios from 'axios';

const BATCH_URL = 'https://batchenrichcandidates-akcoqbr7sa-uc.a.run.app?batchSize=50';
const MAX_ERRORS = 10;

async function runBatch() {
    let totalProcessed = 0;
    let consecutiveErrors = 0;

    console.log('Starting batch enrichment orchestration...');

    while (true) {
        try {
            console.log(`Calling batch function... (Total processed so far: ${totalProcessed})`);
            const response = await axios.get(BATCH_URL, { timeout: 300000 }); // 5 min timeout
            const data = response.data;

            console.log('Batch Result:', JSON.stringify(data));

            if (data.processed) {
                totalProcessed += data.processed;
                consecutiveErrors = 0;
            }

            if (data.processed === 0 && data.remaining === 0) {
                console.log('All candidates processed!');
                break;
            }

            if (data.processed === 0 && data.scanned > 0) {
                console.log('Scanned candidates but found none needing enrichment. We might be done or hitting a gap.');
                // If we scanned 500 (default limit in function) and found 0, we are likely done or need to wait.
                if (data.scanned >= 500) {
                    console.log('Scanned full batch limit and found none. Assuming complete.');
                    break;
                }
            }

            // Safety break
            if (consecutiveErrors > MAX_ERRORS) {
                console.error('Too many consecutive errors. Stopping.');
                break;
            }

            // Sleep 2 seconds to be nice
            await new Promise(resolve => setTimeout(resolve, 2000));

        } catch (error) {
            console.error('Error calling batch function:', error.message);
            consecutiveErrors++;
            await new Promise(resolve => setTimeout(resolve, 5000));
        }
    }

    console.log(`Finished. Total processed in this session: ${totalProcessed}`);
}

runBatch();
