// ── Centralized API client ──────────────────────────────────────────────────

export function getApiBaseUrl(): string {
    if (process.env.NEXT_PUBLIC_API_URL) {
        return process.env.NEXT_PUBLIC_API_URL.replace(/\/+$/, "");
    }
    return "http://localhost:8000";
}

export function getWsUrl(): string {
    if (process.env.NEXT_PUBLIC_WS_URL) {
        return process.env.NEXT_PUBLIC_WS_URL;
    }
    const apiBase = getApiBaseUrl();
    try {
        const url = new URL(apiBase);
        const wsProto = url.protocol === "https:" ? "wss:" : "ws:";
        return `${wsProto}//${url.host}/ws/live`;
    } catch {
        return "ws://localhost:8000/ws/live";
    }
}

export const API_BASE = getApiBaseUrl();
export const WS_URL = getWsUrl();

async function request<T>(path: string, options?: RequestInit): Promise<T> {
    const adminToken = process.env.NEXT_PUBLIC_ADMIN_TOKEN;
    const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(adminToken ? { "X-Admin-Token": adminToken } : {}),
        ...(options?.headers as Record<string, string> || {}),
    };
    const res = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers,
    });
    if (!res.ok) {
        throw new Error(`API ${res.status}: ${res.statusText}`);
    }
    return res.json();
}

// ── Simulation ──────────────────────────────────────────────────────────────

export const api = {
    health: () => request<{ status: string }>("/health"),
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
