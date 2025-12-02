import { onCall, HttpsError } from "firebase-functions/v2/https";
import * as admin from "firebase-admin";
import { z } from "zod";

const firestore = admin.firestore();

// Schema for saving a search
const SaveSearchInputSchema = z.object({
    name: z.string().min(1).max(100),
    query: z.object({
        query_text: z.string().optional(),
        filters: z.record(z.any()).optional(),
        job_description: z.any().optional(), // For job-based searches
    }),
    type: z.enum(["candidate", "job"]).default("candidate"),
});

/**
 * Save a search query for the current user
 */
export const saveSearch = onCall(
    {
        memory: "256MiB",
        timeoutSeconds: 30,
    },
    async (request) => {
        if (!request.auth) {
            throw new HttpsError("unauthenticated", "User must be logged in to save searches");
        }

        const userId = request.auth.uid;

        // Validate input
        let validatedInput;
        try {
            validatedInput = SaveSearchInputSchema.parse(request.data);
        } catch (error) {
            if (error instanceof z.ZodError) {
                throw new HttpsError("invalid-argument", `Invalid input: ${error.errors[0].message}`);
            }
            throw new HttpsError("invalid-argument", "Invalid request data");
        }

        const { name, query, type } = validatedInput;

        try {
            const searchData = {
                userId,
                name,
                query,
                type,
                createdAt: admin.firestore.FieldValue.serverTimestamp(),
                lastUsed: admin.firestore.FieldValue.serverTimestamp(),
            };

            const docRef = await firestore.collection("saved_searches").add(searchData);

            return {
                success: true,
                id: docRef.id,
                ...searchData,
            };
        } catch (error) {
            console.error("Error saving search:", error);
            throw new HttpsError("internal", "Failed to save search");
        }
    }
);

/**
 * Get saved searches for the current user
 */
export const getSavedSearches = onCall(
    {
        memory: "256MiB",
        timeoutSeconds: 30,
    },
    async (request) => {
        if (!request.auth) {
            throw new HttpsError("unauthenticated", "User must be logged in to view saved searches");
        }

        const userId = request.auth.uid;

        try {
            const snapshot = await firestore
                .collection("saved_searches")
                .where("userId", "==", userId)
                .orderBy("createdAt", "desc")
                .get();

            const searches = snapshot.docs.map((doc) => ({
                id: doc.id,
                ...doc.data(),
                // Convert timestamps to ISO strings
                createdAt: (doc.data().createdAt as admin.firestore.Timestamp)?.toDate().toISOString(),
                lastUsed: (doc.data().lastUsed as admin.firestore.Timestamp)?.toDate().toISOString(),
            }));

            return {
                success: true,
                searches,
            };
        } catch (error) {
            console.error("Error fetching saved searches:", error);
            throw new HttpsError("internal", "Failed to fetch saved searches");
        }
    }
);

/**
 * Delete a saved search
 */
export const deleteSavedSearch = onCall(
    {
        memory: "256MiB",
        timeoutSeconds: 30,
    },
    async (request) => {
        if (!request.auth) {
            throw new HttpsError("unauthenticated", "User must be logged in to delete searches");
        }

        const { searchId } = request.data;
        if (!searchId) {
            throw new HttpsError("invalid-argument", "Search ID is required");
        }

        const userId = request.auth.uid;

        try {
            const docRef = firestore.collection("saved_searches").doc(searchId);
            const doc = await docRef.get();

            if (!doc.exists) {
                throw new HttpsError("not-found", "Saved search not found");
            }

            if (doc.data()?.userId !== userId) {
                throw new HttpsError("permission-denied", "You do not have permission to delete this search");
            }

            await docRef.delete();

            return {
                success: true,
                id: searchId,
            };
        } catch (error) {
            console.error("Error deleting saved search:", error);
            throw new HttpsError("internal", "Failed to delete saved search");
        }
    }
);
