import { getApp, getApps, initializeApp, type FirebaseApp } from "firebase/app";
import { getFirestore, type Firestore } from "firebase/firestore";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

const requiredValues = [
  firebaseConfig.apiKey,
  firebaseConfig.authDomain,
  firebaseConfig.projectId,
  firebaseConfig.appId,
];

export const firebaseConfigured = requiredValues.every(Boolean);

let app: FirebaseApp | undefined;
let db: Firestore | undefined;

/**
 * Firebase is optional at build time so a missing local .env never causes a blank page.
 * Mutating controls surface a clear configuration error instead.
 */
export function getFirestoreDb(): Firestore | null {
  if (!firebaseConfigured) return null;

  app ??= getApps().length > 0 ? getApp() : initializeApp(firebaseConfig);
  db ??= getFirestore(app);
  return db;
}
