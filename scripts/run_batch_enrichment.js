const axios = require('axios');

const BASE_URL = 'https://batchenrichcandidates-akcoqbr7sa-uc.a.run.app';
const BATCH_SIZE = 50;
const FORCE_UPDATE = true; // User requested "complete set", so we force update
const MAX_ERRORS = 10;

async function runBatch() {
    let totalProcessed = 0;
    let consecutiveErrors = 0;
    let lastDocId = null;

    console.log(`Starting batch enrichment orchestration (Force: ${FORCE_UPDATE})...`);

    while (true) {
        try {
            let url = `${BASE_URL}?batchSize=${BATCH_SIZE}&force=${FORCE_UPDATE}`;
            if (lastDocId) {
                url += `&startAfter=${lastDocId}`;
            }

            console.log(`Calling batch function... (Total processed: ${totalProcessed}, LastDocId: ${lastDocId || 'START'})`);

            const response = await axios.get(url, { timeout: 300000 }); // 5 min timeout
            const data = response.data;

            console.log('Batch Result:', JSON.stringify(data));

            if (data.processed) {
                totalProcessed += data.processed;
                consecutiveErrors = 0;
            }

            // Update cursor
            if (data.lastDocId) {
                lastDocId = data.lastDocId;
            } else {
                console.log('No lastDocId returned. Assuming end of collection.');
                break;
            }

            // If we scanned 0 docs, we are done
            if (data.scanned === 0) {
                console.log('Scanned 0 docs. Finished.');
                break;
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
