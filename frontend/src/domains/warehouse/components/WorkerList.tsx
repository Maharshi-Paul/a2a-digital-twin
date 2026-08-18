"use client";

import { GlowCard } from "@/core/components/GlowCard";
import { StatusBadge } from "@/core/components/StatusBadge";
import type { WorkerInfo } from "@/core/types";

interface WorkerListProps {
    workers: WorkerInfo[];
}

function getWorkerDotStyle(status: string): string {
    if (status === "IDLE") return "bg-emerald-400";
    if (status === "PICKING") return "bg-amber-400 animate-pulse";
    return "bg-red-400";
}

export function WorkerList({ workers }: WorkerListProps) {
    return (
        <GlowCard>
            <h2 className="text-sm font-semibold text-slate-300 mb-3">Workers</h2>
            <div className="space-y-2 max-h-[250px] overflow-y-auto">
                {workers.map((w) => (
                    <div
                        key={w.id}
                        className="flex items-center justify-between text-xs p-2 rounded-lg bg-slate-800/30"
                    >
                        <div className="flex items-center gap-2">
                            <span className={`w-2 h-2 rounded-full ${getWorkerDotStyle(w.status)}`} />
                            <span className="text-slate-300 font-medium">{w.name}</span>
                        </div>
                        <StatusBadge status={w.status} variant="worker" />
                    </div>
                ))}
            </div>
        </GlowCard>
    );
}
