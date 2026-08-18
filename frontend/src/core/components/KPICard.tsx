interface KPICardProps {
    label: string;
    value: string | number;
    color: "indigo" | "amber" | "emerald" | "red" | "cyan" | "purple";
}

const colorMap: Record<string, string> = {
    indigo: "from-indigo-500/20 to-indigo-500/5 border-indigo-500/20 text-indigo-400",
    amber: "from-amber-500/20 to-amber-500/5 border-amber-500/20 text-amber-400",
    emerald: "from-emerald-500/20 to-emerald-500/5 border-emerald-500/20 text-emerald-400",
    red: "from-red-500/20 to-red-500/5 border-red-500/20 text-red-400",
    cyan: "from-cyan-500/20 to-cyan-500/5 border-cyan-500/20 text-cyan-400",
    purple: "from-purple-500/20 to-purple-500/5 border-purple-500/20 text-purple-400",
};

export function KPICard({ label, value, color }: KPICardProps) {
    const styles = colorMap[color] || colorMap.indigo;
    const valueColor = styles.split(" ").pop();

    return (
        <div className={`bg-gradient-to-b border rounded-xl p-3 ${styles}`}>
            <p className="text-[10px] uppercase tracking-wider text-slate-500 font-medium">
                {label}
            </p>
            <p className={`text-xl font-bold font-mono mt-1 ${valueColor}`}>
                {value}
            </p>
        </div>
    );
}
