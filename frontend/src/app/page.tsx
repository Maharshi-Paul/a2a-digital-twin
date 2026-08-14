"use client";

import { useEffect, useState, useRef, useCallback } from "react";

// ── Types ────────────────────────────────────────────────────────────────────

interface KPI {
  timestamp: string;
  orders: { total: number; by_status: Record<string, number> };
  avg_priority_score: number;
  sla_breached_count: number;
  worker_utilization: number;
  avg_zone_congestion: number;
}

interface QueueEntry {
  order_id: number;
  external_id: string;
  score: number;
  sla_risk: number;
}

interface Zone {
  id: number;
  name: string;
  congestion: number;
}

interface WorkerInfo {
  id: number;
  name: string;
  status: string;
  zone_id: number | null;
  tasks: number;
  pos: number[];
}

interface PackingStation {
  id: number;
  name: string;
  load: number;
  capacity: number;
  status: string;
}

interface AgentLog {
  id: number;
  sender: string;
  receiver: string;
  type: string;
  timestamp: string;
}

interface WSData {
  type: string;
  timestamp: string;
  warehouse: {
    zones: Zone[];
    workers: WorkerInfo[];
    packing_stations: PackingStation[];
    dock_doors: { id: number; name: string; status: string; truck: string | null }[];
  };
  kpis: KPI;
  queue: QueueEntry[];
  agent_logs: AgentLog[];
  connections: number;
}

// ── API Base ────────────────────────────────────────────────────────────────

const API = "http://localhost:8000";
const WS_URL = "ws://localhost:8000/ws/live";

// ── Main Dashboard ──────────────────────────────────────────────────────────

export default function Dashboard() {
  const [wsData, setWsData] = useState<WSData | null>(null);
  const [connected, setConnected] = useState(false);
  const [simRunning, setSimRunning] = useState(false);
  const [simCount, setSimCount] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<NodeJS.Timeout | null>(null);

  // WebSocket connection
  const connectWS = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      console.log("WS connected");
    };

    ws.onmessage = (e) => {
      try {
        const data: WSData =
          e.data instanceof Blob
            ? JSON.parse(new TextDecoder().decode(e.data as unknown as ArrayBuffer))
            : JSON.parse(e.data);
        if (data.type === "state_update") {
          setWsData(data);
        }
      } catch {
        // binary orjson — decode
        if (e.data instanceof Blob) {
          (e.data as Blob).text().then((text) => {
            try {
              const data = JSON.parse(text);
              if (data.type === "state_update") setWsData(data);
            } catch { }
          });
        }
      }
    };

    ws.onclose = () => {
      setConnected(false);
      reconnectTimer.current = setTimeout(connectWS, 3000);
    };
    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    connectWS();
    checkSimStatus();
    return () => {
      wsRef.current?.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };
  }, [connectWS]);

  // Simulation control
  const checkSimStatus = async () => {
    try {
      const res = await fetch(`${API}/api/simulation/status`);
      const data = await res.json();
      setSimRunning(data.running);
      setSimCount(data.total_generated);
    } catch { }
  };

  const seedDB = async () => {
    await fetch(`${API}/api/simulation/seed`, { method: "POST" });
  };

  const toggleSim = async () => {
    const endpoint = simRunning ? "stop" : "start";
    const res = await fetch(`${API}/api/simulation/${endpoint}`, { method: "POST" });
    const data = await res.json();
    setSimRunning(data.status === "started" || data.status === "already_running");
    if (data.total_generated) setSimCount(data.total_generated);
    checkSimStatus();
  };

  const kpis = wsData?.kpis;
  const queue = wsData?.queue || [];
  const zones = wsData?.warehouse?.zones || [];
  const workers = wsData?.warehouse?.workers || [];
  const packing = wsData?.warehouse?.packing_stations || [];
  const docks = wsData?.warehouse?.dock_doors || [];
  const logs = wsData?.agent_logs || [];

  return (
    <div className="min-h-screen p-4 md:p-6 max-w-[1800px] mx-auto">
      {/* Header */}
      <header className="flex flex-col md:flex-row items-start md:items-center justify-between mb-6 gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight">
            <span className="bg-gradient-to-r from-indigo-400 via-purple-400 to-cyan-400 bg-clip-text text-transparent">
              Warehouse Digital Twin
            </span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Smart Agent-to-Agent Queue-Aware Orchestration
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`flex items-center gap-2 text-xs font-medium px-3 py-1.5 rounded-full ${connected
                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                : "bg-red-500/10 text-red-400 border border-red-500/30"
              }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${connected ? "bg-emerald-400 animate-pulse" : "bg-red-400"
                }`}
            />
            {connected ? "LIVE" : "DISCONNECTED"}
          </span>
          <button
            onClick={seedDB}
            className="px-4 py-1.5 bg-slate-700/50 hover:bg-slate-600/50 text-slate-300 text-xs font-medium rounded-lg border border-slate-600/50 transition-all hover:border-slate-500"
          >
            Seed DB
          </button>
          <button
            onClick={toggleSim}
            className={`px-4 py-1.5 text-xs font-semibold rounded-lg border transition-all ${simRunning
                ? "bg-red-500/15 text-red-400 border-red-500/30 hover:bg-red-500/25"
                : "bg-indigo-500/15 text-indigo-400 border-indigo-500/30 hover:bg-indigo-500/25"
              }`}
          >
            {simRunning ? "⏹ Stop Sim" : "▶ Start Sim"}
          </button>
        </div>
      </header>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        <KPICard
          label="Total Orders"
          value={kpis?.orders?.total ?? 0}
          color="indigo"
        />
        <KPICard
          label="Pending"
          value={kpis?.orders?.by_status?.PENDING ?? 0}
          color="amber"
        />
        <KPICard
          label="Dispatched"
          value={kpis?.orders?.by_status?.DISPATCHED ?? 0}
          color="emerald"
        />
        <KPICard
          label="SLA Breached"
          value={kpis?.sla_breached_count ?? 0}
          color="red"
        />
        <KPICard
          label="Worker Util"
          value={`${((kpis?.worker_utilization ?? 0) * 100).toFixed(0)}%`}
          color="cyan"
        />
        <KPICard
          label="Avg Congestion"
          value={`${((kpis?.avg_zone_congestion ?? 0) * 100).toFixed(0)}%`}
          color="purple"
        />
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Priority Queue */}
        <div className="lg:col-span-2 glow-card p-4">
          <h2 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
            Dynamic Priority Queue
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-slate-500 border-b border-slate-700/50">
                  <th className="text-left py-2 px-2 font-medium">#</th>
                  <th className="text-left py-2 px-2 font-medium">Order ID</th>
                  <th className="text-right py-2 px-2 font-medium">Score</th>
                  <th className="text-right py-2 px-2 font-medium">SLA Risk</th>
                  <th className="py-2 px-2 font-medium">Priority</th>
                </tr>
              </thead>
              <tbody>
                {queue.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="text-center py-8 text-slate-500">
                      No orders in queue — seed DB &amp; start simulation
                    </td>
                  </tr>
                ) : (
                  queue.slice(0, 15).map((entry, i) => (
                    <tr
                      key={entry.order_id}
                      className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors animate-slide-in"
                      style={{ animationDelay: `${i * 30}ms` }}
                    >
                      <td className="py-2 px-2 text-slate-500 font-mono">{i + 1}</td>
                      <td className="py-2 px-2 font-mono text-slate-300">
                        {entry.external_id}
                      </td>
                      <td className="py-2 px-2 text-right font-mono text-indigo-400 font-semibold">
                        {entry.score.toFixed(4)}
                      </td>
                      <td className="py-2 px-2 text-right">
                        <span
                          className={`font-mono font-semibold ${entry.sla_risk > 0.7
                              ? "text-red-400"
                              : entry.sla_risk > 0.4
                                ? "text-amber-400"
                                : "text-emerald-400"
                            }`}
                        >
                          {(entry.sla_risk * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td className="py-2 px-2">
                        <PriorityBar score={entry.score} />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Agent Activity Feed */}
        <div className="glow-card p-4">
          <h2 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
            Agent Activity
          </h2>
          <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
            {logs.length === 0 ? (
              <p className="text-xs text-slate-500 text-center py-4">
                No agent activity yet
              </p>
            ) : (
              logs.slice(0, 20).map((log, i) => (
                <div
                  key={log.id}
                  className="text-xs p-2 rounded-lg bg-slate-800/40 border border-slate-700/30 animate-slide-in"
                  style={{ animationDelay: `${i * 20}ms` }}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <AgentBadge name={log.sender} />
                    <span className="text-slate-600">→</span>
                    <AgentBadge name={log.receiver} />
                    <span className="ml-auto text-[10px] text-slate-600 font-mono">
                      {log.timestamp?.split("T")[1]?.split(".")[0] || ""}
                    </span>
                  </div>
                  <span className="status-badge bg-slate-700/50 text-slate-400">
                    {log.type}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Bottom Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
        {/* Zone Heatmap */}
        <div className="glow-card p-4 lg:col-span-2">
          <h2 className="text-sm font-semibold text-slate-300 mb-3">
            Zone Congestion Heatmap
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {zones.map((zone) => (
              <div
                key={zone.id}
                className="p-3 rounded-lg border border-slate-700/30 text-center"
                style={{
                  background: `rgba(${zone.congestion > 0.6
                      ? "239, 68, 68"
                      : zone.congestion > 0.3
                        ? "245, 158, 11"
                        : "16, 185, 129"
                    }, ${0.08 + zone.congestion * 0.2})`,
                }}
              >
                <p className="text-[10px] text-slate-400 truncate">{zone.name}</p>
                <p className="text-lg font-bold font-mono mt-1">
                  {(zone.congestion * 100).toFixed(0)}%
                </p>
                <div className="congestion-bar mt-2">
                  <div
                    className="congestion-fill"
                    style={{
                      width: `${zone.congestion * 100}%`,
                      background:
                        zone.congestion > 0.6
                          ? "#ef4444"
                          : zone.congestion > 0.3
                            ? "#f59e0b"
                            : "#10b981",
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Workers */}
        <div className="glow-card p-4">
          <h2 className="text-sm font-semibold text-slate-300 mb-3">Workers</h2>
          <div className="space-y-2 max-h-[250px] overflow-y-auto">
            {workers.map((w) => (
              <div
                key={w.id}
                className="flex items-center justify-between text-xs p-2 rounded-lg bg-slate-800/30"
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`w-2 h-2 rounded-full ${w.status === "IDLE"
                        ? "bg-emerald-400"
                        : w.status === "PICKING"
                          ? "bg-amber-400 animate-pulse"
                          : "bg-red-400"
                      }`}
                  />
                  <span className="text-slate-300 font-medium">{w.name}</span>
                </div>
                <span
                  className={`status-badge ${w.status === "IDLE"
                      ? "bg-emerald-500/15 text-emerald-400"
                      : w.status === "PICKING"
                        ? "bg-amber-500/15 text-amber-400"
                        : "bg-red-500/15 text-red-400"
                    }`}
                >
                  {w.status}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Packing & Docks */}
        <div className="glow-card p-4">
          <h2 className="text-sm font-semibold text-slate-300 mb-3">
            Stations & Docks
          </h2>
          <div className="space-y-2">
            {packing.map((ps) => (
              <div key={ps.id} className="text-xs">
                <div className="flex justify-between text-slate-400 mb-1">
                  <span>{ps.name}</span>
                  <span className="font-mono">
                    {ps.load}/{ps.capacity}
                  </span>
                </div>
                <div className="congestion-bar">
                  <div
                    className="congestion-fill"
                    style={{
                      width: `${(ps.load / ps.capacity) * 100}%`,
                      background:
                        ps.load >= ps.capacity ? "#ef4444" : "#6366f1",
                    }}
                  />
                </div>
              </div>
            ))}
            <div className="border-t border-slate-700/50 pt-2 mt-2">
              {docks.map((d) => (
                <div
                  key={d.id}
                  className="flex items-center justify-between text-xs py-1"
                >
                  <span className="text-slate-400">{d.name}</span>
                  <span
                    className={`status-badge ${d.status === "FREE"
                        ? "bg-emerald-500/15 text-emerald-400"
                        : "bg-amber-500/15 text-amber-400"
                      }`}
                  >
                    {d.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="mt-6 text-center text-[10px] text-slate-600">
        Warehouse Digital Twin v0.1.0 — Queue Engine cycle every 2s — Powered by
        A2A + MCP
      </footer>
    </div>
  );
}

// ── Components ──────────────────────────────────────────────────────────────

function KPICard({
  label,
  value,
  color,
}: {
  label: string;
  value: string | number;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    indigo: "from-indigo-500/20 to-indigo-500/5 border-indigo-500/20 text-indigo-400",
    amber: "from-amber-500/20 to-amber-500/5 border-amber-500/20 text-amber-400",
    emerald: "from-emerald-500/20 to-emerald-500/5 border-emerald-500/20 text-emerald-400",
    red: "from-red-500/20 to-red-500/5 border-red-500/20 text-red-400",
    cyan: "from-cyan-500/20 to-cyan-500/5 border-cyan-500/20 text-cyan-400",
    purple: "from-purple-500/20 to-purple-500/5 border-purple-500/20 text-purple-400",
  };

  return (
    <div
      className={`bg-gradient-to-b border rounded-xl p-3 ${colorMap[color] || colorMap.indigo
        }`}
    >
      <p className="text-[10px] uppercase tracking-wider text-slate-500 font-medium">
        {label}
      </p>
      <p className={`text-xl font-bold font-mono mt-1 ${colorMap[color]?.split(" ").pop()}`}>
        {value}
      </p>
    </div>
  );
}

function PriorityBar({ score }: { score: number }) {
  const pct = Math.min(100, score * 100);
  return (
    <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
      <div
        className="h-full rounded-full transition-all duration-500"
        style={{
          width: `${pct}%`,
          background: `linear-gradient(90deg, #6366f1, ${pct > 70 ? "#ef4444" : pct > 40 ? "#f59e0b" : "#10b981"
            })`,
        }}
      />
    </div>
  );
}

function AgentBadge({ name }: { name: string }) {
  const colorMap: Record<string, string> = {
    order_coordinator: "bg-indigo-500/20 text-indigo-400",
    inventory_agent: "bg-emerald-500/20 text-emerald-400",
    picking_agent: "bg-amber-500/20 text-amber-400",
    packing_agent: "bg-cyan-500/20 text-cyan-400",
    dock_agent: "bg-purple-500/20 text-purple-400",
    queue_engine: "bg-pink-500/20 text-pink-400",
  };

  return (
    <span
      className={`text-[10px] font-semibold px-2 py-0.5 rounded-md ${colorMap[name] || "bg-slate-700/50 text-slate-400"
        }`}
    >
      {name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
    </span>
  );
}
