interface StatusBadgeProps {
    status: string;
    variant?: "worker" | "dock" | "default";
}

const variantMap: Record<string, Record<string, string>> = {
    worker: {
        IDLE: "bg-emerald-500/15 text-emerald-400",
        PICKING: "bg-amber-500/15 text-amber-400",
        BUSY: "bg-red-500/15 text-red-400",
    },
    dock: {
        FREE: "bg-emerald-500/15 text-emerald-400",
        LOADING: "bg-amber-500/15 text-amber-400",
        OCCUPIED: "bg-amber-500/15 text-amber-400",
    },
    default: {},
};

export function StatusBadge({ status, variant = "default" }: StatusBadgeProps) {
    const statusColors = variantMap[variant] || variantMap.default;
    const color = statusColors[status] || "bg-slate-700/50 text-slate-400";

    return (
        <span className={`status-badge ${color}`}>
            {status}
        </span>
    );
}
