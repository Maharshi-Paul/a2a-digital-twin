interface PriorityBarProps {
    score: number;
}

export function PriorityBar({ score }: PriorityBarProps) {
    const pct = Math.min(100, score * 100);
    return (
        <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
            <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                    width: `${pct}%`,
                    background: `linear-gradient(90deg, #6366f1, ${pct > 70 ? "#ef4444" : pct > 40 ? "#f59e0b" : "#10b981"
                        })`,
                }}
            />
        </div>
    );
}
