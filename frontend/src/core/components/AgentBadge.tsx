const agentColorMap: Record<string, string> = {
    order_coordinator: "bg-indigo-500/20 text-indigo-400",
    inventory_agent: "bg-emerald-500/20 text-emerald-400",
    picking_agent: "bg-amber-500/20 text-amber-400",
    packing_agent: "bg-cyan-500/20 text-cyan-400",
    dock_agent: "bg-purple-500/20 text-purple-400",
    queue_engine: "bg-pink-500/20 text-pink-400",
};

interface AgentBadgeProps {
    name: string;
}

export function AgentBadge({ name }: AgentBadgeProps) {
    return (
        <span
            className={`text-[10px] font-semibold px-2 py-0.5 rounded-md ${agentColorMap[name] || "bg-slate-700/50 text-slate-400"
                }`}
        >
            {name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
        </span>
    );
}
