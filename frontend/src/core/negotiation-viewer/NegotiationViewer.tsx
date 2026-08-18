"use client";

import { useMemo } from "react";
import { GlowCard } from "@/core/components/GlowCard";
import { AgentBadge } from "@/core/components/AgentBadge";
import type { AgentLog } from "@/core/types";

interface NegotiationViewerProps {
    logs: AgentLog[];
}

// Negotiation message types that form conversation flows
const NEGOTIATION_TYPES = new Set([
    "STOCKOUT_ALERT",
    "SUBSTITUTE_OFFER",
    "SUBSTITUTE_ACCEPT",
    "SUBSTITUTE_REJECT",
    "ACK",
    "NACK",
    "TASK_REQUEST",
    "TASK_RESPONSE",
]);

interface NegotiationFlow {
    correlationId: string;
    messages: AgentLog[];
}

function getFlowColor(type: string): string {
    switch (type) {
        case "STOCKOUT_ALERT":
            return "border-l-red-500";
        case "SUBSTITUTE_OFFER":
            return "border-l-amber-500";
        case "SUBSTITUTE_ACCEPT":
        case "ACK":
            return "border-l-emerald-500";
        case "SUBSTITUTE_REJECT":
        case "NACK":
            return "border-l-red-400";
        case "TASK_REQUEST":
            return "border-l-indigo-500";
        case "TASK_RESPONSE":
            return "border-l-cyan-500";
        default:
            return "border-l-slate-500";
    }
}

function getTypeBadgeColor(type: string): string {
    switch (type) {
        case "STOCKOUT_ALERT":
            return "bg-red-500/15 text-red-400";
        case "SUBSTITUTE_OFFER":
            return "bg-amber-500/15 text-amber-400";
        case "SUBSTITUTE_ACCEPT":
        case "ACK":
            return "bg-emerald-500/15 text-emerald-400";
        case "SUBSTITUTE_REJECT":
        case "NACK":
            return "bg-red-500/15 text-red-400";
        case "TASK_REQUEST":
            return "bg-indigo-500/15 text-indigo-400";
        case "TASK_RESPONSE":
            return "bg-cyan-500/15 text-cyan-400";
        default:
            return "bg-slate-700/50 text-slate-400";
    }
}

export function NegotiationViewer({ logs }: NegotiationViewerProps) {
    // Group logs by correlation_id into negotiation flows
    const flows = useMemo<NegotiationFlow[]>(() => {
        const negotiationLogs = logs.filter((l) => NEGOTIATION_TYPES.has(l.type));

        const grouped = new Map<string, AgentLog[]>();
        for (const log of negotiationLogs) {
            const key = log.correlation_id || `single-${log.id}`;
            if (!grouped.has(key)) grouped.set(key, []);
            grouped.get(key)!.push(log);
        }

        return Array.from(grouped.entries())
            .map(([correlationId, messages]) => ({
                correlationId,
                messages: messages.sort(
                    (a, b) =>
                        new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
                ),
            }))
            .slice(0, 8); // Show last 8 flows
    }, [logs]);

    return (
        <GlowCard>
            <h2 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
                Agent Negotiations
            </h2>
            <div className="space-y-3 max-h-[400px] overflow-y-auto pr-1">
                {flows.length === 0 ? (
                    <p className="text-xs text-slate-500 text-center py-4">
                        No negotiations yet — start simulation to see agent interactions
                    </p>
                ) : (
                    flows.map((flow) => (
                        <div
                            key={flow.correlationId}
                            className="rounded-lg bg-slate-800/30 border border-slate-700/20 p-2 animate-fade-in"
                        >
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-[9px] text-slate-600 font-mono">
                                    {flow.correlationId.slice(0, 12)}…
                                </span>
                                <span className="text-[9px] text-slate-600">
                                    {flow.messages.length} msg{flow.messages.length > 1 && "s"}
                                </span>
                            </div>
                            <div className="space-y-1.5">
                                {flow.messages.map((msg, i) => (
                                    <div
                                        key={msg.id}
                                        className={`flex items-center gap-2 text-[11px] pl-2 border-l-2 ${getFlowColor(msg.type)} animate-slide-in`}
                                        style={{ animationDelay: `${i * 50}ms` }}
                                    >
                                        <AgentBadge name={msg.sender} />
                                        <span className="text-slate-600">→</span>
                                        <AgentBadge name={msg.receiver} />
                                        <span
                                            className={`ml-auto text-[9px] font-semibold px-1.5 py-0.5 rounded ${getTypeBadgeColor(msg.type)}`}
                                        >
                                            {msg.type}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))
                )}
            </div>
        </GlowCard>
    );
}
