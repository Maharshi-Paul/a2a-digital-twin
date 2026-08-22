"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/core/api/client";

export function SimulationControls() {
    const [simRunning, setSimRunning] = useState(false);
    const [simCount, setSimCount] = useState(0);

    const checkStatus = useCallback(async () => {
        try {
            const data = await api.simulation.status();
            setSimRunning(data.running);
            setSimCount(data.total_generated);
        } catch {
            /* backend may not be running */
        }
    }, []);

    useEffect(() => {
        // Defer the initial network request so this effect only establishes work,
        // and the async response owns the resulting state update.
        const timer = setTimeout(() => {
            void checkStatus();
        }, 0);
        return () => clearTimeout(timer);
    }, [checkStatus]);

    const seedDB = async () => {
        await api.simulation.seed();
    };

    const toggleSim = async () => {
        const data = simRunning
            ? await api.simulation.stop()
            : await api.simulation.start();
        setSimRunning(
            data.status === "started" || data.status === "already_running"
        );
        if ("total_generated" in data && data.total_generated) {
            setSimCount(data.total_generated as number);
        }
        checkStatus();
    };

    return (
        <div className="flex items-center gap-3">
            <span className="text-[10px] text-slate-500 font-mono tabular-nums">
                {simCount > 0 && `${simCount} orders`}
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
    );
}
