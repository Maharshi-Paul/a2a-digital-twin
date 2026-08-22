import {
  collection,
  doc,
  getDocs,
  increment,
  onSnapshot,
  serverTimestamp,
  writeBatch,
  type DocumentData,
  type QueryDocumentSnapshot,
  type Unsubscribe,
} from "firebase/firestore";
import { getFirestoreDb } from "@/lib/firebase";
import {
  clamp,
  type DispatchLaneRecord,
  type OperationalStatus,
  type PackingStationRecord,
  type WarehouseTwinState,
  type WorkerRecord,
  type ZoneRecord,
} from "./live-twin";

const WAREHOUSES = "warehouses";
const WAREHOUSE_ID = "default";
const COLLECTIONS = ["zones", "stations", "dispatch", "workers"] as const;

type WarehouseCollection = (typeof COLLECTIONS)[number];
type TwinUpdate = Partial<WarehouseTwinState>;

const seededZones: Omit<ZoneRecord, "updatedAt">[] = [
  { id: "zone-a", name: "Zone A", aisleRange: "A1–A6", activeTasks: 3, capacity: 12, activeWorkers: 2 },
  { id: "zone-b", name: "Zone B", aisleRange: "A7–A12", activeTasks: 7, capacity: 12, activeWorkers: 2 },
  { id: "zone-c", name: "Zone C", aisleRange: "A13–A18", activeTasks: 5, capacity: 12, activeWorkers: 1 },
  { id: "zone-d", name: "Zone D", aisleRange: "A19–A24", activeTasks: 2, capacity: 12, activeWorkers: 1 },
];

const seededStations: Omit<PackingStationRecord, "updatedAt">[] = [
  { id: "pack-1", name: "Pack 1", queueDepth: 2, capacity: 8, status: "active" },
  { id: "pack-2", name: "Pack 2", queueDepth: 4, capacity: 8, status: "busy" },
  { id: "pack-3", name: "Pack 3", queueDepth: 1, capacity: 8, status: "ready" },
];

const seededDispatch: Omit<DispatchLaneRecord, "updatedAt">[] = [
  { id: "dispatch-east", name: "Dispatch East", queuedOrders: 5, capacity: 16, readyForPickup: 3, status: "active" },
  { id: "dispatch-west", name: "Dispatch West", queuedOrders: 2, capacity: 16, readyForPickup: 1, status: "ready" },
];

const seededWorkers: Omit<WorkerRecord, "updatedAt">[] = [
  { id: "worker-alice", name: "Alice", zoneId: "zone-a", x: 18, y: 32, status: "active", taskCount: 2 },
  { id: "worker-marcus", name: "Marcus", zoneId: "zone-b", x: 42, y: 28, status: "busy", taskCount: 3 },
  { id: "worker-priya", name: "Priya", zoneId: "zone-b", x: 48, y: 62, status: "active", taskCount: 2 },
  { id: "worker-charlie", name: "Charlie", zoneId: "zone-c", x: 70, y: 34, status: "active", taskCount: 2 },
  { id: "worker-yuki", name: "Yuki", zoneId: "zone-d", x: 83, y: 58, status: "ready", taskCount: 1 },
  { id: "worker-sofia", name: "Sofia", zoneId: "zone-a", x: 24, y: 74, status: "ready", taskCount: 1 },
];

function requireDb() {
  const db = getFirestoreDb();
  if (!db) {
    throw new Error("Firebase is not configured. Add the NEXT_PUBLIC_FIREBASE_* values to frontend/.env.local.");
  }
  return db;
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function asText(value: unknown, fallback: string): string {
  return typeof value === "string" && value.trim().length > 0 ? value : fallback;
}

function asStatus(value: unknown, fallback: OperationalStatus = "idle"): OperationalStatus {
  return value === "idle" || value === "active" || value === "busy" || value === "blocked" || value === "ready"
    ? value
    : fallback;
}

function timestampToString(value: unknown): string | undefined {
  return value && typeof value === "object" && "toDate" in value && typeof value.toDate === "function"
    ? value.toDate().toISOString()
    : undefined;
}

function toZone(snapshot: QueryDocumentSnapshot<DocumentData>): ZoneRecord {
  const data = snapshot.data();
  return {
    id: snapshot.id,
    name: asText(data.name, snapshot.id),
    aisleRange: asText(data.aisleRange, "Unassigned"),
    activeTasks: Math.max(0, asNumber(data.activeTasks)),
    capacity: Math.max(0, asNumber(data.capacity)),
    activeWorkers: Math.max(0, asNumber(data.activeWorkers)),
    updatedAt: timestampToString(data.updatedAt),
  };
}

function toStation(snapshot: QueryDocumentSnapshot<DocumentData>): PackingStationRecord {
  const data = snapshot.data();
  return {
    id: snapshot.id,
    name: asText(data.name, snapshot.id),
    queueDepth: Math.max(0, asNumber(data.queueDepth)),
    capacity: Math.max(0, asNumber(data.capacity)),
    status: asStatus(data.status),
    updatedAt: timestampToString(data.updatedAt),
  };
}

function toDispatch(snapshot: QueryDocumentSnapshot<DocumentData>): DispatchLaneRecord {
  const data = snapshot.data();
  return {
    id: snapshot.id,
    name: asText(data.name, snapshot.id),
    queuedOrders: Math.max(0, asNumber(data.queuedOrders)),
    capacity: Math.max(0, asNumber(data.capacity)),
    readyForPickup: Math.max(0, asNumber(data.readyForPickup)),
    status: asStatus(data.status),
    updatedAt: timestampToString(data.updatedAt),
  };
}

function toWorker(snapshot: QueryDocumentSnapshot<DocumentData>): WorkerRecord {
  const data = snapshot.data();
  return {
    id: snapshot.id,
    name: asText(data.name, snapshot.id),
    zoneId: asText(data.zoneId, "unassigned"),
    x: clamp(asNumber(data.x), 0, 100),
    y: clamp(asNumber(data.y), 0, 100),
    status: asStatus(data.status),
    taskCount: Math.max(0, asNumber(data.taskCount)),
    updatedAt: timestampToString(data.updatedAt),
  };
}

function sorted<T extends { name: string }>(records: T[]): T[] {
  return records.sort((a, b) => a.name.localeCompare(b.name));
}

/** Subscribes directly to Firestore collections; every remote write appears without a refresh. */
export function subscribeToWarehouseTwin(
  onUpdate: (update: TwinUpdate) => void,
  onError: (error: Error) => void,
): Unsubscribe {
  const db = getFirestoreDb();
  if (!db) return () => undefined;

  const reportError = (error: Error) => onError(error);
  const root = doc(db, WAREHOUSES, WAREHOUSE_ID);
  const unsubscribers = [
    onSnapshot(root, (snapshot) => {
      const data = snapshot.data();
      onUpdate({
        meta: {
          running: Boolean(data?.running),
          simulationTick: asNumber(data?.simulationTick),
          updatedAt: timestampToString(data?.updatedAt),
        },
      });
    }, reportError),
    onSnapshot(collection(root, "zones"), (snapshot) => onUpdate({ zones: sorted(snapshot.docs.map(toZone)) }), reportError),
    onSnapshot(collection(root, "stations"), (snapshot) => onUpdate({ stations: sorted(snapshot.docs.map(toStation)) }), reportError),
    onSnapshot(collection(root, "dispatch"), (snapshot) => onUpdate({ dispatchLanes: sorted(snapshot.docs.map(toDispatch)) }), reportError),
    onSnapshot(collection(root, "workers"), (snapshot) => onUpdate({ workers: sorted(snapshot.docs.map(toWorker)) }), reportError),
  ];

  return () => unsubscribers.forEach((unsubscribe) => unsubscribe());
}

async function clearCollection(name: WarehouseCollection): Promise<void> {
  const db = requireDb();
  const snapshot = await getDocs(collection(db, WAREHOUSES, WAREHOUSE_ID, name));
  const batch = writeBatch(db);
  snapshot.docs.forEach((document) => batch.delete(document.ref));
  if (!snapshot.empty) await batch.commit();
}

/** Wipes the dashboard collections then writes a small, documented development dataset. */
export async function seedWarehouseTwin(): Promise<void> {
  await Promise.all(COLLECTIONS.map(clearCollection));

  const db = requireDb();
  const root = doc(db, WAREHOUSES, WAREHOUSE_ID);
  const batch = writeBatch(db);
  batch.set(root, {
    running: false,
    simulationTick: 0,
    seededAt: serverTimestamp(),
    updatedAt: serverTimestamp(),
  });

  seededZones.forEach((zone) => batch.set(doc(root, "zones", zone.id), { ...zone, updatedAt: serverTimestamp() }));
  seededStations.forEach((station) => batch.set(doc(root, "stations", station.id), { ...station, updatedAt: serverTimestamp() }));
  seededDispatch.forEach((lane) => batch.set(doc(root, "dispatch", lane.id), { ...lane, updatedAt: serverTimestamp() }));
  seededWorkers.forEach((worker) => batch.set(doc(root, "workers", worker.id), { ...worker, updatedAt: serverTimestamp() }));
  await batch.commit();
}

function nextStatus(load: number): OperationalStatus {
  if (load >= 0.9) return "blocked";
  if (load >= 0.65) return "busy";
  if (load > 0) return "active";
  return "ready";
}

function step(value: number, min: number, max: number, amount = 2): number {
  return clamp(value + Math.floor(Math.random() * (amount * 2 + 1)) - amount, min, max);
}

/** A browser-owned simulation tick. It intentionally writes to Firestore so every listener sees the same changes. */
export async function runSimulationTick(): Promise<void> {
  const db = requireDb();
  const root = doc(db, WAREHOUSES, WAREHOUSE_ID);
  const [zones, stations, dispatch, workers] = await Promise.all([
    getDocs(collection(root, "zones")),
    getDocs(collection(root, "stations")),
    getDocs(collection(root, "dispatch")),
    getDocs(collection(root, "workers")),
  ]);

  if (zones.empty) {
    throw new Error("No warehouse data exists yet. Select Seed DB before starting the simulation.");
  }

  const batch = writeBatch(db);
  zones.docs.forEach((zone) => {
    const data = zone.data();
    const capacity = Math.max(1, asNumber(data.capacity, 1));
    const activeTasks = step(asNumber(data.activeTasks), 0, capacity);
    batch.update(zone.ref, { activeTasks, updatedAt: serverTimestamp() });
  });
  stations.docs.forEach((station) => {
    const data = station.data();
    const capacity = Math.max(1, asNumber(data.capacity, 1));
    const queueDepth = step(asNumber(data.queueDepth), 0, capacity);
    batch.update(station.ref, {
      queueDepth,
      status: nextStatus(queueDepth / capacity),
      updatedAt: serverTimestamp(),
    });
  });
  dispatch.docs.forEach((lane) => {
    const data = lane.data();
    const capacity = Math.max(1, asNumber(data.capacity, 1));
    const queuedOrders = step(asNumber(data.queuedOrders), 0, capacity);
    batch.update(lane.ref, {
      queuedOrders,
      readyForPickup: step(asNumber(data.readyForPickup), 0, queuedOrders, 1),
      status: nextStatus(queuedOrders / capacity),
      updatedAt: serverTimestamp(),
    });
  });
  workers.docs.forEach((worker) => {
    const data = worker.data();
    const taskCount = step(asNumber(data.taskCount), 0, 5, 1);
    batch.update(worker.ref, {
      x: step(asNumber(data.x), 0, 100, 6),
      y: step(asNumber(data.y), 0, 100, 6),
      taskCount,
      status: nextStatus(taskCount / 5),
      updatedAt: serverTimestamp(),
    });
  });
  batch.set(root, {
    running: true,
    simulationTick: increment(1),
    updatedAt: serverTimestamp(),
  }, { merge: true });
  await batch.commit();
}

export async function setSimulationRunning(running: boolean): Promise<void> {
  const db = requireDb();
  const root = doc(db, WAREHOUSES, WAREHOUSE_ID);
  const batch = writeBatch(db);
  batch.set(root, { running, updatedAt: serverTimestamp() }, { merge: true });
  await batch.commit();
}
