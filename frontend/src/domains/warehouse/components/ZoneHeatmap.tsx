"use client";

import { GlowCard } from "@/core/components/GlowCard";
import type { Zone } from "@/core/types";

interface ZoneHeatmapProps {
    zones: Zone[];
}

function getCongestionColor(level: number): string {
    if (level > 0.6) return "239, 68, 68";   // red
    if (level > 0.3) return "245, 158, 11";   // amber
    return "16, 185, 129";                     // green
}

function getCongestionBarColor(level: number): string {
    if (level > 0.6) return "#ef4444";
    if (level > 0.3) return "#f59e0b";
    return "#10b981";
}

export function ZoneHeatmap({ zones }: ZoneHeatmapProps) {
    return (
        <GlowCard className="lg:col-span-2">
            <h2 className="text-sm font-semibold text-slate-300 mb-3">
                Zone Congestion Heatmap
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {zones.map((zone) => (
                    <div
                        key={zone.id}
                        className="p-3 rounded-lg border border-slate-700/30 text-center"
                        style={{
                            background: `rgba(${getCongestionColor(zone.congestion)}, ${0.08 + zone.congestion * 0.2
                                })`,
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
                                    background: getCongestionBarColor(zone.congestion),
                                }}
                            />
                        </div>
                    </div>
                ))}
            </div>
        </GlowCard>
    );
}
