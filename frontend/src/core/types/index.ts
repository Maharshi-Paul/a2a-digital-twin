// ── Shared TypeScript types for the Warehouse Digital Twin ──────────────────

export interface KPI {
    timestamp: string;
    orders: { total: number; by_status: Record<string, number> };
    avg_priority_score: number;
    sla_breached_count: number;
    worker_utilization: number;
    avg_zone_congestion: number;
}

export interface QueueEntry {
    order_id: number;
    external_id: string;
    score: number;
    sla_risk: number;
    wait_time?: number;
    inventory?: number;
    congestion?: number;
    packing?: number;
    breakdown?: Record<string, number>;
}

export interface Zone {
    id: number;
    name: string;
    congestion: number;
}

export interface WorkerInfo {
    id: number;
    name: string;
    status: string;
    zone_id: number | null;
    tasks: number;
    pos: number[];
}

export interface PackingStation {
    id: number;
    name: string;
    load: number;
    capacity: number;
    status: string;
}

export interface DockDoor {
    id: number;
    name: string;
    status: string;
    truck: string | null;
}

export interface AgentLog {
    id: number;
    sender: string;
    receiver: string;
    type: string;
    correlation_id?: string;
    payload?: Record<string, unknown>;
    timestamp: string;
}

export interface WSData {
    type: string;
    timestamp: string;
    warehouse: {
        zones: Zone[];
        workers: WorkerInfo[];
        packing_stations: PackingStation[];
        dock_doors: DockDoor[];
    };
    kpis: KPI;
    queue: QueueEntry[];
    agent_logs: AgentLog[];
    connections: number;
}

export interface SimulationStatus {
    running: boolean;
    total_generated: number;
}
