"use client";

import { GlowCard } from "@/core/components/GlowCard";
import { PriorityBar } from "@/core/components/PriorityBar";
import type { QueueEntry } from "@/core/types";

interface PriorityQueueProps {
    queue: QueueEntry[];
}

export function PriorityQueue({ queue }: PriorityQueueProps) {
    return (
        <GlowCard className="lg:col-span-2">
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
                                    <td className="py-2 px-2 text-slate-500 font-mono">
                                        {i + 1}
                                    </td>
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
        </GlowCard>
    );
}
