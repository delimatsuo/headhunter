import { onRequest } from "firebase-functions/v2/https";
import * as admin from "firebase-admin";

// Ensure admin is initialized (it might be in index.ts but safe to check/init)
if (!admin.apps.length) {
    admin.initializeApp();
}

const db = admin.firestore();

export const countCPO = onRequest({
    memory: "2GiB",
    timeoutSeconds: 300,
}, async (req, res) => {
    try {
        console.log("Starting Firestore scan for CPO candidates...");

        const candidatesSnapshot = await db.collection("candidates").get();
        let processed = 0;
        let hasOrgId = 0;
        let sampleOrgIds = new Set();

        let counts = {
            "CPO": 0,
            "Head of Product": 0,
            "VP Product": 0
        };

        // Stream candidates
        // The snapshot is already fetched as candidatesSnapshot

        candidatesSnapshot.forEach(doc => {
            processed++;
            const data = doc.data();
            if (data.org_id) {
                hasOrgId++;
                if (sampleOrgIds.size < 5) sampleOrgIds.add(data.org_id);
            }

            // ... count logic ...
            const title = (
                data.current_title ||
                data.job_title ||
                data.title ||
                data.resume_analysis?.current_role ||
                data.intelligent_analysis?.role_based_competencies?.current_role_competencies?.role ||
                ""
            ).toLowerCase();

            if (title.includes("chief product officer") || (title.includes("cpo") && !title.includes("expo"))) { // Added !title.includes("expo") back
                counts.CPO++;
            }
            if (title.includes("head of product")) {
                counts["Head of Product"]++;
            }
            if (title.includes("vp of product") || title.includes("vice president of product") || title.includes("vp product")) {
                counts["VP Product"]++;
            }
        });

        res.status(200).json({
            total_candidates: processed,
            org_id_stats: {
                count_with_org_id: hasOrgId,
                sample_org_ids: Array.from(sampleOrgIds)
            },
            counts: {
                "Chief Product Officer": counts.CPO,
                "CPO": counts.CPO, // Duplicate just for clarity in view
                "Head of Product": counts["Head of Product"],
                "VP Product": counts["VP Product"]
            },
            message: "Scanned Firestore candidates collection"
        });

    } catch (err: any) {
        console.error(err);
        res.status(500).send(err.message);
    }
});
