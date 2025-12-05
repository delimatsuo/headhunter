import { onCall, HttpsError } from "firebase-functions/v2/https";
import * as admin from "firebase-admin";
import { z } from "zod";

const firestore = admin.firestore();

// Validation Schemas
const SwitchOrgSchema = z.object({
    targetOrgId: z.string().min(1),
});

const CreateClientOrgSchema = z.object({
    name: z.string().min(1).max(100),
    ownerEmail: z.string().email().optional(),
    ownerId: z.string().optional(),
});

/**
 * Switch the user's active organization context
 * Updates custom claims and user profile
 */
export const switchOrganization = onCall(
    {
        memory: "256MiB",
        timeoutSeconds: 30,
    },
    async (request) => {
        // Check authentication
        if (!request.auth) {
            throw new HttpsError("unauthenticated", "Authentication required");
        }

        const userId = request.auth.uid;

        // Validate input
        let validatedInput;
        try {
            validatedInput = SwitchOrgSchema.parse(request.data);
        } catch (error) {
            if (error instanceof z.ZodError) {
                throw new HttpsError("invalid-argument", `Invalid input: ${error.errors[0].message}`);
            }
            throw new HttpsError("invalid-argument", "Invalid request data");
        }

        const { targetOrgId } = validatedInput;

        try {
            // 1. Verify user is a member of the target organization
            const orgDoc = await firestore.collection("organizations").doc(targetOrgId).get();

            if (!orgDoc.exists) {
                throw new HttpsError("not-found", "Organization not found");
            }

            const orgData = orgDoc.data();
            const members = orgData?.members || [];

            if (!members.includes(userId)) {
                throw new HttpsError("permission-denied", "You are not a member of this organization");
            }

            // 2. Get user's current role/permissions (preserve them or fetch specific org role if implemented)
            // For now, we assume role is consistent across orgs or stored in user profile
            const userDoc = await firestore.collection("users").doc(userId).get();
            const userData = userDoc.data();
            const role = userData?.role || "admin";
            const permissions = userData?.permissions || { admin: true };

            // 3. Update Custom Claims
            await admin.auth().setCustomUserClaims(userId, {
                org_id: targetOrgId,
                role: role,
                permissions: permissions
            });

            // 4. Update User Profile (to persist selection)
            await firestore.collection("users").doc(userId).update({
                organization_id: targetOrgId
            });

            console.log(`User ${userId} switched to organization ${targetOrgId}`);

            return {
                success: true,
                organization_id: targetOrgId,
                organization_name: orgData?.name
            };

        } catch (error) {
            console.error(`Error switching organization for user ${userId}:`, error);
            if (error instanceof HttpsError) throw error;
            throw new HttpsError("internal", "Failed to switch organization");
        }
    }
);

/**
 * Create a new Client Organization (Admin only)
 */
export const createClientOrganization = onCall(
    {
        memory: "512MiB",
        timeoutSeconds: 60,
    },
    async (request) => {
        // Check authentication
        if (!request.auth) {
            throw new HttpsError("unauthenticated", "Authentication required");
        }

        // Verify Admin role (or Ella Recruiter)
        // In a real app, check request.auth.token.role === 'admin' or specific permission
        // For now, we assume any authenticated user can create (or restrict via UI)
        // Ideally: if (!request.auth.token.permissions?.admin) throw new HttpsError("permission-denied", ...);

        const creatorId = request.auth.uid;

        // Validate input
        let validatedInput;
        try {
            validatedInput = CreateClientOrgSchema.parse(request.data);
        } catch (error) {
            if (error instanceof z.ZodError) {
                throw new HttpsError("invalid-argument", `Invalid input: ${error.errors[0].message}`);
            }
            throw new HttpsError("invalid-argument", "Invalid request data");
        }

        const { name, ownerEmail, ownerId } = validatedInput;

        try {
            const orgId = `org_client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

            // Determine initial members
            const members = [creatorId];
            if (ownerId && ownerId !== creatorId) {
                members.push(ownerId);
            }

            // If ownerEmail provided, we might need to look up UID or invite (skipping invite logic for now)
            if (ownerEmail) {
                try {
                    const userRecord = await admin.auth().getUserByEmail(ownerEmail);
                    if (userRecord && !members.includes(userRecord.uid)) {
                        members.push(userRecord.uid);
                    }
                } catch (e) {
                    console.log(`User with email ${ownerEmail} not found, skipping add to members`);
                }
            }

            // Create Organization
            await firestore.collection("organizations").doc(orgId).set({
                id: orgId,
                name: name,
                type: "client",
                owner_id: ownerId || creatorId,
                members: members,
                settings: {
                    max_candidates: 1000,
                    features: ["candidate_search"]
                },
                created_at: admin.firestore.FieldValue.serverTimestamp(),
                updated_at: admin.firestore.FieldValue.serverTimestamp(),
                created_by: creatorId
            });

            // If the creator is an Ella user, they should be added to the org but maybe not switched immediately
            // Update creator's organizations list
            await firestore.collection("users").doc(creatorId).update({
                organizations: admin.firestore.FieldValue.arrayUnion(orgId)
            });

            if (ownerId && ownerId !== creatorId) {
                await firestore.collection("users").doc(ownerId).update({
                    organizations: admin.firestore.FieldValue.arrayUnion(orgId)
                });
            }

            console.log(`Created client organization ${orgId} (${name})`);

            return {
                success: true,
                organization_id: orgId,
                organization_name: name
            };

        } catch (error) {
            console.error("Error creating client organization:", error);
            throw new HttpsError("internal", "Failed to create organization");
        }
    }
);
