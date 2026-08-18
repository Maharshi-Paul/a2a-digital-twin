"use client";

import { useWebSocket } from "@/core/hooks/useWebSocket";
import { KPICard } from "@/core/components/KPICard";
import { NegotiationViewer } from "@/core/negotiation-viewer/NegotiationViewer";
import { SimulationControls } from "../components/SimulationControls";
import { PriorityQueue } from "../components/PriorityQueue";
import { AgentActivityFeed } from "../components/AgentActivityFeed";
import { ZoneHeatmap } from "../components/ZoneHeatmap";
import { WorkerList } from "../components/WorkerList";
import { StationsDocks } from "../components/StationsDocks";

export function DashboardView() {
    const { data: wsData, connected } = useWebSocket();

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
                    <SimulationControls />
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

            {/* Main Grid — Queue + Agent Activity */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <PriorityQueue queue={queue} />
                <AgentActivityFeed logs={logs} />
            </div>

            {/* Middle Grid — Negotiation Viewer */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-4">
                <NegotiationViewer logs={logs} />
                <ZoneHeatmap zones={zones} />
            </div>

            {/* Bottom Grid — Workers + Stations */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
                <WorkerList workers={workers} />
                <StationsDocks packing={packing} docks={docks} />
            </div>

            {/* Footer */}
            <footer className="mt-6 text-center text-[10px] text-slate-600">
                Warehouse Digital Twin v1.0.0 — Queue Engine cycle every 2s — Powered by
                A2A + MCP
            </footer>
        </div>
    );
}
