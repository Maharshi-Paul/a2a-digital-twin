"use client";

import { GlowCard } from "@/core/components/GlowCard";
import { StatusBadge } from "@/core/components/StatusBadge";
import type { PackingStation, DockDoor } from "@/core/types";

interface StationsDocksProps {
    packing: PackingStation[];
    docks: DockDoor[];
}

export function StationsDocks({ packing, docks }: StationsDocksProps) {
    return (
        <GlowCard>
            <h2 className="text-sm font-semibold text-slate-300 mb-3">
                Stations &amp; Docks
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
                                    background: ps.load >= ps.capacity ? "#ef4444" : "#6366f1",
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
                            <StatusBadge status={d.status} variant="dock" />
                        </div>
                    ))}
                </div>
            </div>
        </GlowCard>
    );
}
