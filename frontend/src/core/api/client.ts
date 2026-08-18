// ── Centralized API client ──────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws/live";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE}${path}`, {
        headers: { "Content-Type": "application/json" },
        ...options,
    });
    if (!res.ok) {
        throw new Error(`API ${res.status}: ${res.statusText}`);
    }
    return res.json();
}

// ── Simulation ──────────────────────────────────────────────────────────────

export const api = {
    simulation: {
        status: () => request<{ running: boolean; total_generated: number }>("/api/simulation/status"),
        seed: () => request<{ status: string; counts: Record<string, number> }>("/api/simulation/seed", { method: "POST" }),
        start: () => request<{ status: string }>("/api/simulation/start", { method: "POST" }),
        stop: () => request<{ status: string; total_generated?: number }>("/api/simulation/stop", { method: "POST" }),
    },
    orders: {
        list: (limit = 50, offset = 0) => request<unknown[]>(`/api/orders?limit=${limit}&offset=${offset}`),
        counts: () => request<{ total: number; by_status: Record<string, number> }>("/api/orders/counts"),
    },
    warehouse: {
        status: () => request<unknown>("/api/warehouse/status"),
        kpis: () => request<unknown>("/api/warehouse/kpis"),
    },
    agents: {
        logs: (limit = 50) => request<unknown[]>(`/api/agent-logs?limit=${limit}`),
    },
    queue: {
        status: () => request<unknown>("/api/queue"),
    },
};
