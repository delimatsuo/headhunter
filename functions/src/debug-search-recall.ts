
import * as admin from "firebase-admin";
import { VectorSearchService } from "./vector-search";

// Initialize Firebase Admin (required for Firestore)
if (admin.apps.length === 0) {
    admin.initializeApp({
        projectId: "headhunter-ai-0088", // Hardcoded for local debug
    });
}

async function debugSearch() {
    const vectorSearch = new VectorSearchService();

    console.log("\n--- DEBUGGING SEARCH RECALL: 'Chief Technology Officer' ---\n");

    const query = {
        // Semantic Anchor: We use the exact title we expect to find
        query_text: "JOB TITLE: Chief Technology Officer\nROLE: Strategic Executive Engineering Leadership",
        limit: 200, // Request EXTRA large batch to see the tail
        filters: {
            // No filters to test raw recall
        }
    };

    try {
        // 1. Run Vector Search
        console.time("Vector Search");
        const results = await vectorSearch.searchCandidates(query);
        console.timeEnd("Vector Search");

        console.log(`\nFound ${results.length} candidates from Vector Search.\n`);

        // 2. Print Top Results with Details
        console.log("RANK | SCORE | NAME | CURRENT ROLE | COMPANY");
        console.log("-".repeat(80));

        for (const [index, result] of results.entries()) {
            const metadata = result.metadata as any;

            let name = metadata.name || "Unknown";
            let role = metadata.current_role || "Unknown Role";
            let company = metadata.current_company || "Unknown Company";

            // If metadata is sparse, fetch from Firestore
            if (name === "Unknown") {
                try {
                    const doc = await admin.firestore().collection('candidates').doc(result.candidate_id).get();
                    if (doc.exists) {
                        const data = doc.data();
                        name = data?.name || name;
                        role = data?.current_role || data?.role || role;
                        company = data?.current_company || data?.company || company;
                    }
                } catch (e) {
                    console.warn(`Failed to fetch doc for ${result.candidate_id}`);
                }
            }

            console.log(`#${index + 1} | ${(result.similarity_score * 100).toFixed(1)}% | ${name} | ${role} | ${company}`);
        }

    } catch (error) {
        console.error("Search failed:", error);
    }
}

debugSearch();
