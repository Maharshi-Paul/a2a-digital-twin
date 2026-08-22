export type OperationalStatus = "idle" | "active" | "busy" | "blocked" | "ready";

export interface ZoneRecord {
  id: string;
  name: string;
  aisleRange: string;
  activeTasks: number;
  capacity: number;
  activeWorkers: number;
  updatedAt?: string;
}

export interface PackingStationRecord {
  id: string;
  name: string;
  queueDepth: number;
  capacity: number;
  status: OperationalStatus;
  updatedAt?: string;
}

export interface DispatchLaneRecord {
  id: string;
  name: string;
  queuedOrders: number;
  capacity: number;
  readyForPickup: number;
  status: OperationalStatus;
  updatedAt?: string;
}

export interface WorkerRecord {
  id: string;
  name: string;
  zoneId: string;
  x: number;
  y: number;
  status: OperationalStatus;
  taskCount: number;
  updatedAt?: string;
}

export interface WarehouseMeta {
  running: boolean;
  simulationTick: number;
  updatedAt?: string;
}

export interface WarehouseTwinState {
  meta: WarehouseMeta;
  zones: ZoneRecord[];
  stations: PackingStationRecord[];
  dispatchLanes: DispatchLaneRecord[];
  workers: WorkerRecord[];
}

export const EMPTY_WAREHOUSE_STATE: WarehouseTwinState = {
  meta: { running: false, simulationTick: 0 },
  zones: [],
  stations: [],
  dispatchLanes: [],
  workers: [],
};

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

/**
 * Task density is the source of truth for a zone's live busyness badge.
 * A full task queue is always 100%, even if malformed upstream data exceeds capacity.
 */
export function getZoneBusyness(zone: Pick<ZoneRecord, "activeTasks" | "capacity">): number {
  if (zone.capacity <= 0) return 0;
  return Math.round(clamp(zone.activeTasks / zone.capacity, 0, 1) * 100);
}

export function getLoadPercent(
  record: Pick<PackingStationRecord, "queueDepth" | "capacity"> | Pick<DispatchLaneRecord, "queuedOrders" | "capacity">
): number {
  if (record.capacity <= 0) return 0;
  const load = "queueDepth" in record ? record.queueDepth : record.queuedOrders;
  return Math.round(clamp(load / record.capacity, 0, 1) * 100);
}

export function getBusynessLabel(percent: number): "Free" | "Busy" | "Congested" {
  if (percent >= 70) return "Congested";
  if (percent >= 40) return "Busy";
  return "Free";
}
