import { Firestore } from '@google-cloud/firestore';

import { getConfig } from './config';

let firestoreClient: Firestore | null = null;

export function getFirestore(): Firestore {
  if (!firestoreClient) {
    const config = getConfig();

    if (config.firestore.emulatorHost) {
      process.env.FIRESTORE_EMULATOR_HOST = process.env.FIRESTORE_EMULATOR_HOST ?? config.firestore.emulatorHost;
    }

    firestoreClient = new Firestore({ projectId: config.firestore.projectId });
  }

  return firestoreClient;
}

export function resetFirestoreForTesting(): void {
  firestoreClient = null;
}
