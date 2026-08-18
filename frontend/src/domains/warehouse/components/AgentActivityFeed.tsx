"use client";

import { GlowCard } from "@/core/components/GlowCard";
import { AgentBadge } from "@/core/components/AgentBadge";
import type { AgentLog } from "@/core/types";

interface AgentActivityFeedProps {
    logs: AgentLog[];
}

export function AgentActivityFeed({ logs }: AgentActivityFeedProps) {
    return (
        <GlowCard>
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
        </GlowCard>
    );
}
