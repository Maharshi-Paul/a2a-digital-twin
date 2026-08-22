# Warehouse Digital Twin frontend

## Run locally

1. Copy [.env.local.example](.env.local.example) to `.env.local` and paste your Firebase Web App configuration.
2. In Firebase Firestore, allow your authenticated development user to read and write the `warehouses/default` document and its `zones`, `stations`, `dispatch`, and `workers` subcollections. Do not use open rules in production.
3. Run `npm install`, then `npm run dev`.

The dashboard renders a clear setup message until Firebase is configured; it does not use local mock telemetry. **Seed DB** replaces the development data with Zones, Pack 1–3, Dispatch lanes, and worker coordinates. **Start Sim** starts a browser-local loop that writes new task metrics and worker positions to Firestore every 2.5 seconds; every connected dashboard receives those changes through Firestore listeners.

## Verify

```bash
npm run lint
npm run build
```
