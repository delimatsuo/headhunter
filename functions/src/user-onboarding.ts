#!/usr/bin/env node
/**
 * User Onboarding Functions
 * Handle new user registration, organization creation, and custom claims
 */

import { onCall, HttpsError, CallableRequest } from "firebase-functions/v2/https";
import { beforeUserCreated, AuthBlockingEvent } from "firebase-functions/v2/identity";
import * as admin from "firebase-admin";
import { z } from "zod";

const firestore = admin.firestore();

// Validation Schema
const OnboardUserSchema = z.object({
  displayName: z.string().min(1).max(100).optional(),
  organizationName: z.string().min(1).max(100).optional(),
});

/**
 * Trigger that runs before a user is created
 * Sets up organization and custom claims for new users
 */
export const handleNewUser = beforeUserCreated(async (event: AuthBlockingEvent) => {
  const user = event.data;
  if (!user) {
    console.error("No user data in event");
    return {};
  }

  console.log(`Setting up new user: ${user.email}`);

  try {
    // Create a default organization for the user
    const orgId = `org_${user.uid}_${Date.now()}`;
    const organizationName = user.displayName
      ? `${user.displayName}'s Organization`
      : `${user.email?.split('@')[0]}'s Organization`;

    // Create organization document
    await firestore.collection('organizations').doc(orgId).set({
      id: orgId,
      name: organizationName,
      owner_id: user.uid,
      members: [user.uid],
      settings: {
        max_candidates: 10000,
        max_searches_per_month: 1000,
        features: ['candidate_search', 'analytics', 'exports']
      },
      created_at: admin.firestore.FieldValue.serverTimestamp(),
      updated_at: admin.firestore.FieldValue.serverTimestamp()
    });

    // Create user profile document
    await firestore.collection('users').doc(user.uid).set({
      uid: user.uid,
      email: user.email,
      displayName: user.displayName || user.email?.split('@')[0],
      organization_id: orgId,
      role: 'admin',
      permissions: {
        can_view_candidates: true,
        can_edit_candidates: true,
        can_delete_candidates: true,
        admin: true
      },
      created_at: admin.firestore.FieldValue.serverTimestamp(),
      updated_at: admin.firestore.FieldValue.serverTimestamp()
    });

    // Set custom claims - this is critical for API access
    await admin.auth().setCustomUserClaims(user.uid, {
      org_id: orgId,
      role: 'admin',
      permissions: {
        can_view_candidates: true,
        can_edit_candidates: true,
        can_delete_candidates: true,
        admin: true
      }
    });

    console.log(`Successfully onboarded user ${user.email} with org ${orgId}`);

    return {
      customClaims: {
        org_id: orgId,
        role: 'admin'
      }
    };
  } catch (error) {
    console.error(`Error onboarding user ${user.email}:`, error);
    // Don't throw error here as it would prevent user creation
    // The user can be onboarded later via the manual endpoint
    return {};
  }
});

/**
 * Manual onboarding endpoint for users who weren't automatically onboarded
 */
export const completeOnboarding = onCall(
  {
    memory: "512MiB",
    timeoutSeconds: 60,
  },
  async (request: CallableRequest) => {
    // Check if user is authenticated
    if (!request.auth) {
      throw new HttpsError("unauthenticated", "Authentication required");
    }

    const userId = request.auth.uid;
    const userEmail = request.auth.token.email || request.auth.token.firebase?.identities?.email?.[0];

    // Validate input
    let validatedInput;
    try {
      validatedInput = OnboardUserSchema.parse(request.data || {});
    } catch (error) {
      if (error instanceof z.ZodError) {
        throw new HttpsError("invalid-argument", `Invalid input: ${error.errors[0].message}`);
      }
      throw new HttpsError("invalid-argument", "Invalid request data");
    }

    try {
      // Check if user already has an organization
      const userDoc = await firestore.collection('users').doc(userId).get();

      // Define standard admin permissions
      const adminPermissions = {
        can_view_candidates: true,
        can_edit_candidates: true,
        can_delete_candidates: true,
        admin: true
      };

      if (userDoc.exists && userDoc.data()?.organization_id) {
        // User already onboarded, just refresh their custom claims and ensure permissions are correct
        const userData = userDoc.data()!;

        // Update Firestore permissions if they are missing or in wrong format (array vs object)
        if (Array.isArray(userData.permissions) || !userData.permissions) {
          await userDoc.ref.update({
            permissions: adminPermissions
          });
        }

        await admin.auth().setCustomUserClaims(userId, {
          org_id: userData.organization_id,
          role: userData.role || 'admin',
          permissions: adminPermissions
        });

        return {
          success: true,
          message: "User already onboarded, refreshed access",
          organization_id: userData.organization_id
        };
      }

      // Create a new organization for the user
      const orgId = `org_${userId}_${Date.now()}`;
      const organizationName = validatedInput.organizationName ||
        validatedInput.displayName ? `${validatedInput.displayName}'s Organization` :
        userEmail ? `${userEmail.split('@')[0]}'s Organization` :
          'My Organization';

      // Create organization document
      await firestore.collection('organizations').doc(orgId).set({
        id: orgId,
        name: organizationName,
        owner_id: userId,
        members: [userId],
        settings: {
          max_candidates: 10000,
          max_searches_per_month: 1000,
          features: ['candidate_search', 'analytics', 'exports']
        },
        created_at: admin.firestore.FieldValue.serverTimestamp(),
        updated_at: admin.firestore.FieldValue.serverTimestamp()
      });

      // Create or update user profile document
      await firestore.collection('users').doc(userId).set({
        uid: userId,
        email: userEmail,
        displayName: validatedInput.displayName || userEmail?.split('@')[0] || 'User',
        organization_id: orgId,
        role: 'admin',
        permissions: adminPermissions,
        created_at: admin.firestore.FieldValue.serverTimestamp(),
        updated_at: admin.firestore.FieldValue.serverTimestamp()
      }, { merge: true });

      // Set custom claims - this enables API access
      await admin.auth().setCustomUserClaims(userId, {
        org_id: orgId,
        role: 'admin',
        permissions: adminPermissions
      });

      console.log(`Successfully completed onboarding for user ${userEmail} with org ${orgId}`);

      return {
        success: true,
        message: "Onboarding completed successfully",
        organization_id: orgId,
        organization_name: organizationName
      };

    } catch (error) {
      console.error(`Error completing onboarding for user ${userId}:`, error);
      throw new HttpsError("internal", "Failed to complete onboarding");
    }
  }
);

/**
 * Get user onboarding status
 */
export const getOnboardingStatus = onCall(
  {
    memory: "256MiB",
    timeoutSeconds: 30,
  },
  async (request: CallableRequest) => {
    // Check if user is authenticated
    if (!request.auth) {
      throw new HttpsError("unauthenticated", "Authentication required");
    }

    const userId = request.auth.uid;
    const customClaims = request.auth.token;

    try {
      // Check if user has custom claims
      const hasOrgClaim = !!customClaims.org_id;

      // Check if user document exists
      const userDoc = await firestore.collection('users').doc(userId).get();
      const hasUserDoc = userDoc.exists;

      // Check if organization exists
      let hasOrganization = false;
      let organizationData = null;

      if (hasOrgClaim) {
        const orgDoc = await firestore.collection('organizations').doc(customClaims.org_id).get();
        hasOrganization = orgDoc.exists;
        organizationData = orgDoc.exists ? orgDoc.data() : null;
      }

      const isFullyOnboarded = hasOrgClaim && hasUserDoc && hasOrganization;

      return {
        success: true,
        onboarding_status: {
          is_onboarded: isFullyOnboarded,
          has_custom_claims: hasOrgClaim,
          has_user_document: hasUserDoc,
          has_organization: hasOrganization,
          organization_id: customClaims.org_id || null,
          organization_name: organizationData?.name || null,
          user_role: customClaims.role || null,
          next_steps: isFullyOnboarded ? [] : [
            !hasOrgClaim && "Complete onboarding to get access",
            !hasUserDoc && "Create user profile",
            !hasOrganization && "Create organization"
          ].filter(Boolean)
        }
      };

    } catch (error) {
      console.error(`Error getting onboarding status for user ${userId}:`, error);
      throw new HttpsError("internal", "Failed to get onboarding status");
    }
  }
);