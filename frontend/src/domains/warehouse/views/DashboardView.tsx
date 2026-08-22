"use client";

import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { firebaseConfigured } from "@/lib/firebase";
import { useWarehouseTwin } from "../hooks/useWarehouseTwin";
import {
  getBusynessLabel,
  getLoadPercent,
  getZoneBusyness,
  clamp,
  type OperationalStatus,
  type ZoneRecord,
} from "../live-twin";
import {
  Activity, Package, CheckCircle2, Users, Timer, AlertTriangle,
  TrendingUp, TrendingDown, Play, Square, Database, Sun, Moon,
  Sparkles, X, Radio, MapPin, Truck, Boxes, PackageCheck, Gauge,
  SlidersHorizontal, Bell, BellOff, Target, Bot, Send, Wifi, WifiOff,
} from "lucide-react";
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar,
  LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";
import styles from "./DashboardView.module.css";

/* ============================== DESIGN TOKENS ============================== */
const C = {
  blue: "#3b82f6",
  cyan: "#22d3ee",
  purple: "#a855f7",
  emerald: "#10b981",
  orange: "#f97316",
  red: "#ef4444",
  textDim: "#8b93a7",
};

/* ============================== AGENT CONFIG ============================== */
const AGENTS = [
  { id: "coordinator", name: "Coordinator", color: C.blue },
  { id: "inventory", name: "Inventory", color: C.cyan },
  { id: "picking", name: "Picking", color: C.purple },
  { id: "packing", name: "Packing", color: C.emerald },
  { id: "dispatch", name: "Dispatch", color: C.orange },
] as const;

const AGENT_LINES: Record<string, string[]> = {
  coordinator: [
    "Re-ranking queue — 3 orders breach SLA within 6 min.",
    "Rebalancing picker assignments across Zone B.",
    "Escalating priority tier for busiest zone.",
  ],
  inventory: [
    "Stock confirmed — all SKUs in Aisle {aisle}.",
    "Low stock flag on bin C{aisle}-14, reorder triggered.",
    "Inventory sync complete, 1,204 SKUs verified.",
  ],
  picking: [
    "Alice en route to Aisle {aisle}, ETA 42s.",
    "Pick path optimized — saved 18s vs. baseline.",
    "Congestion detected in Aisle {aisle}, rerouting worker.",
  ],
  packing: [
    "Station 2 accepting next order now.",
    "Packing throughput steady at 94% efficiency.",
    "Station 3 free — ready for next order.",
  ],
  dispatch: [
    "Courier assigned, pickup in 3 min.",
    "Dock 1 loading — 2 orders staged.",
    "Dispatch rate holding at 96%.",
  ],
};

/* ============================== MAP GEOMETRY ============================== */
const GRID_W = 1200, GRID_H = 620;
const SHELF_ROWS = 4, SHELF_COLS = 6;
const SHELF_W = 100, SHELF_H = 80;
const SHELF_AREA_LEFT = 90;            // left margin for zone labels
const SHELF_AREA_RIGHT = 680;          // total width shelves occupy
const SHELF_GAP_X = (SHELF_AREA_RIGHT - SHELF_COLS * SHELF_W) / (SHELF_COLS - 1);
const SHELF_AREA_TOP = 50;
const SHELF_AREA_BOTTOM = GRID_H - 50;
const SHELF_GAP_Y = (SHELF_AREA_BOTTOM - SHELF_AREA_TOP - SHELF_ROWS * SHELF_H) / (SHELF_ROWS - 1);
const ZONE_LABELS = ["A", "B", "C", "D"];
const ZONE_COLORS = ["#3b82f6", "#a855f7", "#f97316", "#22d3ee"];

// Packing / Dispatch area starts after shelves with clear gap
const OPS_LEFT = SHELF_AREA_LEFT + SHELF_AREA_RIGHT + 50;  // 820
const PACK_W = 110, PACK_H = 80, PACK_GAP = 20;
const DISPATCH_LEFT = OPS_LEFT + PACK_W + 40;               // 970
const DISPATCH_W = 80, DISPATCH_H = 240;

function shelfPos(r: number, c: number) {
  return {
    x: SHELF_AREA_LEFT + c * (SHELF_W + SHELF_GAP_X),
    y: SHELF_AREA_TOP + r * (SHELF_H + SHELF_GAP_Y),
  };
}

/* ============================== HELPERS ============================== */
type Theme = "light" | "dark";

function useInterval(cb: () => void, delay: number | null) {
  const ref = useRef(cb);
  ref.current = cb;
  useEffect(() => {
    if (delay == null) return;
    const id = setInterval(() => ref.current(), delay);
    return () => clearInterval(id);
  }, [delay]);
}

function formatTime(date: Date) {
  return date.toLocaleTimeString([], { hour12: false });
}

function statusColor(status: OperationalStatus) {
  if (status === "blocked") return C.red;
  if (status === "busy") return C.orange;
  if (status === "active") return C.cyan;
  return C.emerald;
}

function busynessColor(pct: number) {
  if (pct >= 70) return C.red;
  if (pct >= 40) return C.orange;
  return C.emerald;
}

/* ============================== ANIMATED NUMBER ============================== */
function AnimatedNumber({ value, decimals = 0 }: { value: number; decimals?: number }) {
  const [display, setDisplay] = useState(value);
  const raf = useRef<number>(0);
  const from = useRef(value);
  useEffect(() => {
    const start = performance.now();
    const startVal = from.current;
    cancelAnimationFrame(raf.current);
    function tick(now: number) {
      const p = clamp((now - start) / 700, 0, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplay(startVal + (value - startVal) * eased);
      if (p < 1) raf.current = requestAnimationFrame(tick);
      else from.current = value;
    }
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [value]);
  return <>{display.toFixed(decimals)}</>;
}

/* ============================== KPI CARD ============================== */
interface KpiDef {
  key: string; label: string; icon: typeof Package; color: string; unit: string;
}

function KpiCard({ def, value, spark, trend }: { def: KpiDef; value: number; spark: { i: number; v: number }[]; trend: number }) {
  const Icon = def.icon;
  const up = trend >= 0;
  const decimals = def.unit === "%" ? 1 : 0;
  return (
    <div className={styles.kpiCard} style={{ "--glow": def.color } as React.CSSProperties}>
      <div className={styles.kpiTop}>
        <div className={styles.kpiIcon} style={{ background: `${def.color}22`, color: def.color }}>
          <Icon size={16} strokeWidth={2.2} />
        </div>
        <div className={`${styles.kpiTrend} ${up ? styles.trendUp : styles.trendDown}`}>
          {up ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
          <span>{Math.abs(trend).toFixed(1)}%</span>
        </div>
      </div>
      <div className={styles.kpiValue}>
        <AnimatedNumber value={value} decimals={decimals} />
        <span className={styles.kpiUnit}>{def.unit}</span>
      </div>
      <div className={styles.kpiLabel}>{def.label}</div>
      <div className={styles.kpiSpark}>
        <ResponsiveContainer width="100%" height={34}>
          <AreaChart data={spark}>
            <defs>
              <linearGradient id={`grad-${def.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={def.color} stopOpacity={0.55} />
                <stop offset="100%" stopColor={def.color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <Area type="monotone" dataKey="v" stroke={def.color} strokeWidth={1.75}
              fill={`url(#grad-${def.key})`} isAnimationActive={true} animationDuration={600} dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/* ============================== WAREHOUSE MAP ============================== */
function WarehouseMap({ zones, workers }: { zones: ZoneRecord[]; workers: { id: string; name: string; x: number; y: number; status: OperationalStatus; color: string }[] }) {
  const [zoom, setZoom] = useState(1);
  const [hover, setHover] = useState<{ id: number; zone: string; col: number; congestion: number } | null>(null);

  const shelves = useMemo(() => {
    return Array.from({ length: SHELF_ROWS * SHELF_COLS }, (_, i) => {
      const r = Math.floor(i / SHELF_COLS), c = i % SHELF_COLS;
      const { x, y } = shelfPos(r, c);
      const zoneIdx = Math.min(r, zones.length - 1);
      const zone = zones[zoneIdx];
      const congestion = zone ? getZoneBusyness(zone) / 100 : 0.2;
      const jitter = ((i % 3) - 1) * 0.08;
      const zoneLabel = ZONE_LABELS[r] ?? ZONE_LABELS[ZONE_LABELS.length - 1];
      return { id: i, x, y, zone: zoneLabel, col: c + 1, congestion: clamp(congestion + jitter, 0.05, 0.95) };
    });
  }, [zones]);

  // Packing station vertical distribution — centered in the grid
  const packStations = [0, 1, 2].map(i => {
    const totalH = 3 * PACK_H + 2 * PACK_GAP;
    const startY = (GRID_H - totalH) / 2;
    return { x: OPS_LEFT, y: startY + i * (PACK_H + PACK_GAP), label: `PACK ${i + 1}` };
  });

  // Dispatch dock — centered vertically
  const dockY = (GRID_H - DISPATCH_H) / 2;

  return (
    <div className={styles.mapWrap}>
      <div className={styles.mapToolbar}>
        <MapPin size={14} />
        <span>Facility 04 · Zone A–D</span>
        <div className={styles.mapZoom}>
          <button type="button" onClick={() => setZoom(z => clamp(z - 0.15, 0.7, 1.6))}>−</button>
          <span>{Math.round(zoom * 100)}%</span>
          <button type="button" onClick={() => setZoom(z => clamp(z + 0.15, 0.7, 1.6))}>+</button>
        </div>
      </div>
      <svg viewBox={`0 0 ${GRID_W} ${GRID_H}`} className={styles.mapSvg}>
        <defs>
          <pattern id="grid" width="28" height="28" patternUnits="userSpaceOnUse">
            <path d="M 28 0 L 0 0 0 28" fill="none" stroke="rgba(255,255,255,0.035)" strokeWidth="1" />
          </pattern>
          <filter id="glowSoft" x="-60%" y="-60%" width="220%" height="220%">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        <g transform={`translate(${GRID_W / 2},${GRID_H / 2}) scale(${zoom}) translate(${-GRID_W / 2},${-GRID_H / 2})`}>
          <rect width={GRID_W} height={GRID_H} fill="url(#grid)" />

          {/* ── Zone row labels & horizontal separators ── */}
          {ZONE_LABELS.map((label, r) => {
            const rowY = SHELF_AREA_TOP + r * (SHELF_H + SHELF_GAP_Y);
            const zoneColor = ZONE_COLORS[r];
            return (
              <g key={label}>
                {/* Zone label pill */}
                <rect x={8} y={rowY + SHELF_H / 2 - 16} width={64} height={32} rx={8}
                  fill={`${zoneColor}18`} stroke={zoneColor} strokeOpacity={0.4} strokeWidth={1.2} />
                <text x={40} y={rowY + SHELF_H / 2 + 5} textAnchor="middle"
                  fill={zoneColor} fontSize="14" fontWeight="700" letterSpacing="0.06em">
                  Zone {label}
                </text>
                {/* Horizontal zone divider (below row, except last) */}
                {r < SHELF_ROWS - 1 && (
                  <line x1={SHELF_AREA_LEFT} y1={rowY + SHELF_H + SHELF_GAP_Y / 2}
                    x2={SHELF_AREA_LEFT + SHELF_AREA_RIGHT} y2={rowY + SHELF_H + SHELF_GAP_Y / 2}
                    stroke={zoneColor} strokeOpacity={0.15} strokeWidth={1} strokeDasharray="6 4" />
                )}
              </g>
            );
          })}

          {/* ── Vertical separator between shelves & operations area ── */}
          <line x1={OPS_LEFT - 25} y1={30} x2={OPS_LEFT - 25} y2={GRID_H - 30}
            stroke="rgba(255,255,255,0.08)" strokeWidth={1} strokeDasharray="4 6" />
          <text x={OPS_LEFT - 25} y={22} textAnchor="middle" fill="rgba(255,255,255,0.3)" fontSize="11" fontWeight="600">
            OPS →
          </text>

          {/* ── Shelves (compartments) ── */}
          {shelves.map(s => {
            const color = busynessColor(s.congestion * 100);
            const compartmentId = `${s.zone}-${s.col}`;
            return (
              <g key={s.id} onMouseEnter={() => setHover(s)} onMouseLeave={() => setHover(null)} style={{ cursor: "pointer" }}>
                <rect x={s.x} y={s.y} width={SHELF_W} height={SHELF_H} rx={8}
                  fill="rgba(255,255,255,0.045)" stroke={color} strokeOpacity={0.55}
                  strokeWidth={hover?.id === s.id ? 2.5 : 1.2}
                  style={{ filter: hover?.id === s.id ? "url(#glowSoft)" : "none", transition: "stroke .6s ease" }} />
                {/* Bottom busyness bar */}
                <rect x={s.x + 4} y={s.y + SHELF_H - 8} width={SHELF_W - 8} height={4} rx={2} fill={color} opacity={0.8} />
                {/* Compartment ID */}
                <text x={s.x + SHELF_W / 2} y={s.y + 22} textAnchor="middle"
                  fill="rgba(255,255,255,0.7)" fontSize="14" fontWeight="700">{compartmentId}</text>
                {/* Congestion % */}
                <text x={s.x + SHELF_W / 2} y={s.y + 42} textAnchor="middle"
                  fill={color} fontSize="12" fontWeight="600">{Math.round(s.congestion * 100)}%</text>
                {/* Status dot */}
                <circle cx={s.x + SHELF_W / 2} cy={s.y + 58} r={4} fill={color} opacity={0.65} />
              </g>
            );
          })}

          {/* ── Packing Stations ── */}
          {packStations.map((ps, i) => (
            <g key={i}>
              <rect x={ps.x} y={ps.y} width={PACK_W} height={PACK_H} rx={12}
                fill="rgba(16,185,129,0.08)" stroke={C.emerald} strokeOpacity={0.5} strokeWidth={1.5} />
              <text x={ps.x + PACK_W / 2} y={ps.y + PACK_H / 2 - 6} textAnchor="middle"
                fill={C.emerald} fontSize="15" fontWeight="700">{ps.label}</text>
              <text x={ps.x + PACK_W / 2} y={ps.y + PACK_H / 2 + 14} textAnchor="middle"
                fill="rgba(16,185,129,0.55)" fontSize="11" fontWeight="500">Station</text>
            </g>
          ))}

          {/* ── Arrow from packing to dispatch ── */}
          <line x1={OPS_LEFT + PACK_W + 6} y1={GRID_H / 2} x2={DISPATCH_LEFT - 6} y2={GRID_H / 2}
            stroke="rgba(249,115,22,0.35)" strokeWidth={1.5} markerEnd="url(#arrowOrange)" />
          <defs>
            <marker id="arrowOrange" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-auto">
              <path d="M 0 0 L 10 5 L 0 10 z" fill={C.orange} opacity={0.6} />
            </marker>
          </defs>

          {/* ── Dispatch Dock ── */}
          <rect x={DISPATCH_LEFT} y={dockY} width={DISPATCH_W} height={DISPATCH_H} rx={12}
            fill="rgba(249,115,22,0.06)" stroke={C.orange} strokeOpacity={0.5} strokeWidth={1.5} />
          <text x={DISPATCH_LEFT + DISPATCH_W / 2} y={dockY + DISPATCH_H / 2 - 8} textAnchor="middle"
            fill={C.orange} fontSize="15" fontWeight="700" transform={`rotate(90 ${DISPATCH_LEFT + DISPATCH_W / 2} ${dockY + DISPATCH_H / 2 - 8})`}>
            DISPATCH
          </text>
          <text x={DISPATCH_LEFT + DISPATCH_W / 2} y={dockY + DISPATCH_H / 2 + 16} textAnchor="middle"
            fill={C.orange} fontSize="13" fontWeight="600" transform={`rotate(90 ${DISPATCH_LEFT + DISPATCH_W / 2} ${dockY + DISPATCH_H / 2 + 16})`}>
            DOCK
          </text>
          {/* Dock bay markers */}
          {[0, 1, 2].map(i => (
            <g key={i}>
              <rect x={DISPATCH_LEFT + DISPATCH_W - 12} y={dockY + 30 + i * 70} width={8} height={40} rx={3}
                fill={C.orange} opacity={0.2} />
              <text x={DISPATCH_LEFT + DISPATCH_W + 12} y={dockY + 55 + i * 70} textAnchor="start"
                fill="rgba(249,115,22,0.5)" fontSize="10" fontWeight="600">Bay {i + 1}</text>
            </g>
          ))}

          {/* ── Workers ── */}
          {workers.map(w => (
            <g key={w.id} style={{ transform: `translate(${w.x * GRID_W / 100}px, ${w.y * GRID_H / 100}px)`, transition: "transform 1.4s ease" }}>
              <circle r={11} fill={w.color} opacity={0.15} className={styles.workerPulse} />
              <circle r={6.5} fill={w.color} filter="url(#glowSoft)" />
              <text x={0} y={-14} textAnchor="middle" fontSize="12" fill="rgba(255,255,255,0.85)" fontWeight="700">{w.name}</text>
            </g>
          ))}
        </g>
      </svg>
      {hover && (
        <div className={styles.mapTooltip}>
          <div className={styles.mtTitle}>Zone {hover.zone} · Shelf {hover.zone}-{hover.col}</div>
          <div className={styles.mtRow}>
            <span>Congestion</span>
            <b style={{ color: busynessColor(hover.congestion * 100) }}>{Math.round(hover.congestion * 100)}%</b>
          </div>
        </div>
      )}
      <div className={styles.mapLegend}>
        <span><i style={{ background: C.emerald }} /> Free</span>
        <span><i style={{ background: C.orange }} /> Busy</span>
        <span><i style={{ background: C.red }} /> Congested</span>
      </div>
    </div>
  );
}

/* ============================== QUEUE CARD ============================== */
function QueueCard({ zone, rank }: { zone: ZoneRecord; rank: number }) {
  const busyness = getZoneBusyness(zone);
  const pct = clamp(busyness, 4, 96);
  const critical = busyness >= 70;
  const color = critical ? C.red : busyness >= 40 ? C.orange : C.emerald;
  return (
    <div className={`${styles.queueCard} ${critical ? styles.critical : ""}`}>
      <div className={styles.qcRing}>
        <svg viewBox="0 0 36 36">
          <circle cx="18" cy="18" r="15.5" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="3" />
          <circle cx="18" cy="18" r="15.5" fill="none" stroke={color}
            strokeWidth="3" strokeDasharray={`${pct} 100`} strokeLinecap="round" transform="rotate(-90 18 18)"
            style={{ transition: "stroke-dasharray 1s ease" }} />
        </svg>
        <span>{busyness}%</span>
      </div>
      <div className={styles.qcBody}>
        <div className={styles.qcTop}>
          <span className={styles.qcId}>{zone.name}</span>
          <span className={`${styles.qcBadge} ${critical ? styles.bRed : busyness >= 40 ? styles.bOrange : styles.bBlue}`}>
            P{Math.max(1, 95 - rank * 10)}
          </span>
        </div>
        <div className={styles.qcMeta}>{zone.aisleRange}</div>
        <div className={styles.qcMeta}>
          <span>{zone.activeTasks} tasks</span>
          <span>·</span>
          <span>{zone.activeWorkers} pickers</span>
          <span>·</span>
          <span style={{ color }}>{getBusynessLabel(busyness)}</span>
        </div>
      </div>
    </div>
  );
}

/* ============================== AI DECISION ENGINE ============================== */
function DecisionEngine({ zone }: { zone?: ZoneRecord }) {
  if (!zone) return <p className={styles.panelEmpty}>Waiting for zone data…</p>;
  const busyness = getZoneBusyness(zone);
  const reasons = [
    { text: `Task density at ${busyness}% — highest workload`, ok: busyness < 70 },
    { text: `${zone.activeWorkers} workers active in zone`, ok: zone.activeWorkers > 0 },
    { text: "Pick path optimized — saved 18s vs baseline", ok: true },
    { text: "Packing station available", ok: true },
    { text: `${zone.activeTasks} active tasks being processed`, ok: true },
  ];
  return (
    <div className={styles.decisionPanel}>
      <div className={styles.decisionHead}>
        <Sparkles size={15} color={C.purple} />
        <span>Prioritizing <b>{zone.name}</b></span>
      </div>
      <div className={styles.decisionTimeline}>
        {reasons.map((r, i) => (
          <div key={i} className={styles.dlItem} style={{ animationDelay: `${i * 0.12}s` }}>
            <div className={styles.dlDot} style={{ background: r.ok ? C.emerald : C.orange }} />
            <span>{r.text}</span>
          </div>
        ))}
      </div>
      <div className={styles.decisionEta}>
        <span>Simulation tick</span>
        <b>{zone.activeTasks} tasks</b>
      </div>
    </div>
  );
}

/* ============================== AGENT CHAT ============================== */
function AgentChat({ messages }: { messages: { agent: string; text: string }[] }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages.length]);
  return (
    <div className={styles.chatPanel}>
      <div className={styles.chatAgents}>
        {AGENTS.map(a => (
          <div key={a.id} className={styles.chatAgentChip}>
            <span className={styles.dotOnline} style={{ background: a.color }} />
            {a.name}
          </div>
        ))}
      </div>
      <div className={styles.chatBody}>
        {messages.map((m, i) => {
          const agent = AGENTS.find(a => a.id === m.agent) ?? AGENTS[0];
          return (
            <div key={i} className={styles.chatBubbleRow}>
              <div className={styles.chatAvatar} style={{ background: `${agent.color}22`, color: agent.color, borderColor: `${agent.color}55` }}>
                {agent.name[0]}
              </div>
              <div className={styles.chatBubble} style={{ borderColor: `${agent.color}33` }}>
                <div className={styles.chatName} style={{ color: agent.color }}>{agent.name}</div>
                <div>{m.text}</div>
              </div>
            </div>
          );
        })}
        <div ref={endRef} />
      </div>
    </div>
  );
}

/* ============================== LIVE ANALYTICS ============================== */
function LiveAnalytics({ throughput, congestion }: { throughput: { t: string; ai: number; fifo: number }[]; congestion: { t: string; v: number }[] }) {
  const [tab, setTab] = useState("throughput");
  return (
    <div className={styles.analyticsPanel}>
      <div className={styles.analyticsTabs}>
        {[{ id: "throughput", label: "Throughput" }, { id: "congestion", label: "Congestion" }, { id: "sla", label: "SLA" }].map(t => (
          <button key={t.id} type="button" className={tab === t.id ? styles.tabActive : ""} onClick={() => setTab(t.id)}>{t.label}</button>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={170}>
        {tab === "throughput" ? (
          <LineChart data={throughput}>
            <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis dataKey="t" stroke={C.textDim} fontSize={10} tickLine={false} axisLine={false} />
            <YAxis stroke={C.textDim} fontSize={10} tickLine={false} axisLine={false} width={26} />
            <Tooltip contentStyle={{ background: "#0b0f1e", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, fontSize: 12 }} />
            <Line type="monotone" dataKey="ai" stroke={C.cyan} strokeWidth={2} dot={false} name="AI Mode" />
            <Line type="monotone" dataKey="fifo" stroke={C.textDim} strokeWidth={1.5} dot={false} strokeDasharray="4 3" name="FIFO" />
          </LineChart>
        ) : tab === "congestion" ? (
          <BarChart data={congestion}>
            <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis dataKey="t" stroke={C.textDim} fontSize={10} tickLine={false} axisLine={false} />
            <YAxis stroke={C.textDim} fontSize={10} tickLine={false} axisLine={false} width={26} />
            <Tooltip contentStyle={{ background: "#0b0f1e", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, fontSize: 12 }} />
            <Bar dataKey="v" radius={[4, 4, 0, 0]} fill={C.orange} />
          </BarChart>
        ) : (
          <AreaChart data={throughput}>
            <defs>
              <linearGradient id="slaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={C.emerald} stopOpacity={0.5} />
                <stop offset="100%" stopColor={C.emerald} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis dataKey="t" stroke={C.textDim} fontSize={10} tickLine={false} axisLine={false} />
            <YAxis stroke={C.textDim} fontSize={10} tickLine={false} axisLine={false} width={26} domain={[0, 100]} />
            <Tooltip contentStyle={{ background: "#0b0f1e", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, fontSize: 12 }} />
            <Area type="monotone" dataKey="ai" stroke={C.emerald} fill="url(#slaGrad)" strokeWidth={2} dot={false} name="SLA %" />
          </AreaChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

/* ============================== ALERT STACK ============================== */
function AlertStack({ alerts, onDismiss }: { alerts: { id: number; level: string; text: string }[]; onDismiss: (id: number) => void }) {
  return (
    <div className={styles.alertStack}>
      {alerts.map(a => (
        <div key={a.id} className={`${styles.alertToast} ${a.level === "crit" ? styles.alertCrit : styles.alertWarn}`}>
          <AlertTriangle size={14} />
          <span>{a.text}</span>
          <button type="button" onClick={() => onDismiss(a.id)}><X size={12} /></button>
        </div>
      ))}
    </div>
  );
}

/* ============================== MAIN DASHBOARD ============================== */
export function DashboardView() {
  const [theme, setTheme] = useState<Theme>("light");
  const [now, setNow] = useState(new Date());
  const [speed, setSpeed] = useState(1);
  const [alertsOn, setAlertsOn] = useState(true);
  const [comparison, setComparison] = useState(false);

  const {
    state, connected, connectionError, actionError, isSeeding, isStarting, seed, start, stop,
  } = useWarehouseTwin();

  // Apply theme
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);

  // Clock
  useInterval(() => setNow(new Date()), 1000);

  // Computed KPIs from Firestore data
  const summary = useMemo(() => {
    const activeTasks = state.zones.reduce((t, z) => t + z.activeTasks, 0);
    const zoneCapacity = state.zones.reduce((t, z) => t + z.capacity, 0);
    const packed = state.stations.reduce((t, s) => t + s.queueDepth, 0);
    const dispatchQueued = state.dispatchLanes.reduce((t, l) => t + l.queuedOrders, 0);
    const readyForPickup = state.dispatchLanes.reduce((t, l) => t + l.readyForPickup, 0);
    const liveWorkers = state.workers.filter(w => w.status === "active" || w.status === "busy").length;
    const avgBusyness = state.zones.length
      ? Math.round(state.zones.reduce((t, z) => t + getZoneBusyness(z), 0) / state.zones.length)
      : 0;
    const packingEff = state.stations.length
      ? Math.round((1 - state.stations.reduce((t, s) => t + getLoadPercent(s), 0) / state.stations.length / 100) * 100)
      : 0;
    const dispatchRate = state.dispatchLanes.length
      ? Math.round((readyForPickup / Math.max(1, dispatchQueued + readyForPickup)) * 100)
      : 0;
    return { activeTasks, zoneCapacity, packed, dispatchQueued, readyForPickup, liveWorkers, avgBusyness, packingEff, dispatchRate };
  }, [state]);

  // KPI definitions with live values
  const KPI_DEFS: KpiDef[] = [
    { key: "totalTasks", label: "Total Tasks", icon: Package, color: C.blue, unit: "" },
    { key: "pending", label: "Pending Queue", icon: Timer, color: C.orange, unit: "" },
    { key: "ready", label: "Ready to Ship", icon: CheckCircle2, color: C.emerald, unit: "" },
    { key: "busyness", label: "Zone Busyness", icon: Gauge, color: C.cyan, unit: "%" },
    { key: "workers", label: "Active Workers", icon: Users, color: C.purple, unit: "" },
    { key: "capacity", label: "Zone Capacity", icon: Activity, color: C.blue, unit: "" },
    { key: "congestion", label: "Congestion", icon: AlertTriangle, color: C.red, unit: "%" },
    { key: "packing", label: "Packing Eff.", icon: PackageCheck, color: C.emerald, unit: "%" },
    { key: "dispatch", label: "Dispatch Rate", icon: Truck, color: C.orange, unit: "%" },
  ];

  const kpiValues: Record<string, number> = {
    totalTasks: summary.activeTasks,
    pending: summary.dispatchQueued + summary.packed,
    ready: summary.readyForPickup,
    busyness: summary.avgBusyness,
    workers: summary.liveWorkers,
    capacity: summary.zoneCapacity,
    congestion: summary.avgBusyness,
    packing: summary.packingEff,
    dispatch: summary.dispatchRate,
  };

  // KPI sparklines (generated from tick history)
  const [kpiSparks, setKpiSparks] = useState<Record<string, { i: number; v: number }[]>>(() =>
    Object.fromEntries(KPI_DEFS.map(d => [d.key, Array.from({ length: 16 }, (_, i) => ({ i, v: 40 + Math.random() * 40 }))]))
  );
  const [kpiTrends, setKpiTrends] = useState<Record<string, number>>(() =>
    Object.fromEntries(KPI_DEFS.map(d => [d.key, (Math.random() - 0.3) * 4]))
  );

  // Update sparklines when data changes
  useEffect(() => {
    setKpiSparks(prev => {
      const next: Record<string, { i: number; v: number }[]> = {};
      for (const d of KPI_DEFS) {
        const arr = prev[d.key] ?? [];
        const v = kpiValues[d.key] ?? 0;
        next[d.key] = [...arr.slice(-15), { i: (arr.at(-1)?.i ?? 0) + 1, v: Math.max(0, v) }];
      }
      return next;
    });
    setKpiTrends(prev => {
      const next: Record<string, number> = {};
      for (const d of KPI_DEFS) {
        const old = prev[d.key] ?? 0;
        const v = kpiValues[d.key] ?? 0;
        next[d.key] = v > 0 ? ((Math.random() - 0.3) * 4) : old;
      }
      return next;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.meta.simulationTick]);

  // Analytics data
  const [throughput, setThroughput] = useState(() =>
    Array.from({ length: 14 }, (_, i) => ({ t: `${i}m`, ai: 60 + Math.random() * 30, fifo: 40 + Math.random() * 20 }))
  );
  const [congestionSeries, setCongestionSeries] = useState(() =>
    Array.from({ length: 14 }, (_, i) => ({ t: `${i}m`, v: Math.round(20 + Math.random() * 60) }))
  );

  // Update analytics on sim tick
  useEffect(() => {
    if (state.meta.simulationTick <= 0) return;
    setThroughput(prev => {
      const t = `${(parseInt(prev[prev.length - 1].t) + 1) % 60}m`;
      const ai = clamp(prev[prev.length - 1].ai + (Math.random() - 0.4) * 8, 40, 100);
      const fifo = clamp(prev[prev.length - 1].fifo + (Math.random() - 0.5) * 6, 20, 70);
      return [...prev.slice(1), { t, ai, fifo }];
    });
    setCongestionSeries(prev => {
      const t = prev[prev.length - 1].t;
      const v = clamp(prev[prev.length - 1].v + (Math.random() - 0.5) * 20, 5, 95);
      return [...prev.slice(1), { t, v }];
    });
  }, [state.meta.simulationTick]);

  // Agent chat simulation
  const [chat, setChat] = useState([
    { agent: "coordinator", text: "Re-ranking queue — 3 orders breach SLA within 6 min." },
    { agent: "inventory", text: "Stock confirmed — all SKUs verified." },
  ]);
  const chatCursor = useRef(0);

  useEffect(() => {
    if (state.meta.simulationTick <= 0) return;
    const agent = AGENTS[chatCursor.current % AGENTS.length];
    chatCursor.current++;
    const lines = AGENT_LINES[agent.id];
    const line = lines[Math.floor(Math.random() * lines.length)]
      .replace("{aisle}", String(Math.floor(Math.random() * 24) + 1));
    setChat(c => [...c.slice(-11), { agent: agent.id, text: line }]);
  }, [state.meta.simulationTick]);

  // Alerts
  const [alerts, setAlerts] = useState<{ id: number; level: string; text: string }[]>([]);
  const alertIdRef = useRef(1);

  useEffect(() => {
    if (state.meta.simulationTick <= 0 || !alertsOn) return;
    if (Math.random() > 0.6) {
      const pool = [
        { level: "warn", text: "Congestion building in Zone B (Aisles 7-12)" },
        { level: "crit", text: "Worker offline — reassigning tasks" },
        { level: "warn", text: "Inventory low on bin C4-11" },
        { level: "crit", text: "SLA risk detected for active zone" },
      ];
      const a = pool[Math.floor(Math.random() * pool.length)];
      const id = alertIdRef.current++;
      setAlerts(prev => [...prev.slice(-3), { id, ...a }]);
      setTimeout(() => setAlerts(prev => prev.filter(x => x.id !== id)), 6000);
    }
  }, [state.meta.simulationTick, alertsOn]);

  const dismissAlert = useCallback((id: number) => setAlerts(prev => prev.filter(a => a.id !== id)), []);

  // Map workers with colors
  const mapWorkers = useMemo(() =>
    state.workers.map((w, i) => ({
      ...w,
      color: [C.cyan, C.purple, C.emerald, C.orange, C.blue, "#f472b6"][i % 6],
    })),
    [state.workers]
  );

  const busiestZone = state.zones.reduce<ZoneRecord | undefined>(
    (cur, z) => (!cur || getZoneBusyness(z) > getZoneBusyness(cur) ? z : cur), undefined,
  );

  const sortedZones = useMemo(() =>
    [...state.zones].sort((a, b) => getZoneBusyness(b) - getZoneBusyness(a)),
    [state.zones]
  );

  const warehouseEmpty = state.zones.length === 0;

  return (
    <div className={styles.twinRoot}>
      {/* Background particles */}
      <div className={styles.bgParticles}>
        {Array.from({ length: 24 }).map((_, i) => (
          <span key={i} style={{ left: `${(i * 41) % 100}%`, animationDelay: `${i * 0.7}s`, animationDuration: `${10 + (i % 6)}s` }} />
        ))}
      </div>

      {/* TOP NAV */}
      <header className={styles.topnav}>
        <div className={styles.tnLeft}>
          <div className={styles.tnLogo}><Boxes size={18} /></div>
          <div>
            <div className={styles.tnTitle}>Warehouse Digital Twin</div>
            <div className={styles.tnSub}>Multi-Agent Mission Control</div>
          </div>
          <div className={`${styles.livePill} ${connected ? styles.liveConnected : ""}`}>
            <span className={styles.liveDot} />
            {connected ? "LIVE (FIRESTORE SYNC)" : firebaseConfigured ? "SYNCING…" : "OFFLINE"}
          </div>
        </div>
        <div className={styles.tnCenter}>
          <div className={styles.clock}>{formatTime(now)}</div>
          <div className={styles.speedControl}>
            {[1, 2, 4].map(s => (
              <button key={s} type="button" className={speed === s ? styles.speedActive : ""} onClick={() => setSpeed(s)}>{s}x</button>
            ))}
          </div>
        </div>
        <div className={styles.tnRight}>
          <button type="button" className={styles.btnTheme} onClick={() => setTheme(t => t === "light" ? "dark" : "light")}>
            {theme === "light" ? <Moon size={14} /> : <Sun size={14} />}
            {theme === "light" ? "Dark Mode" : "Light Mode"}
          </button>
          <button type="button" className={styles.btnGhost} onClick={() => void seed()} disabled={!firebaseConfigured || isSeeding}>
            <Database size={14} />{isSeeding ? "Seeding…" : "DB"}
          </button>
          {state.meta.running ? (
            <button type="button" className={styles.btnDanger} onClick={() => void stop()}>
              <Square size={14} />Stop
            </button>
          ) : (
            <button type="button" className={styles.btnPrimary} onClick={() => void start()} disabled={!firebaseConfigured || isStarting}>
              <Play size={14} />{isStarting ? "Starting…" : "Sim"}
            </button>
          )}
          <button type="button" className={styles.iconBtn} onClick={() => setAlertsOn(a => !a)}>
            {alertsOn ? <Bell size={15} /> : <BellOff size={15} />}
          </button>
        </div>
      </header>

      {/* Error notice */}
      {(connectionError || actionError) && (
        <div className={styles.notice} role="alert">
          <AlertTriangle size={14} />
          <span><strong>{connectionError ? "Firestore unavailable:" : "Action failed:"}</strong> {connectionError || actionError}</span>
        </div>
      )}

      {/* KPI STRIP */}
      <section className={styles.kpiStrip}>
        {KPI_DEFS.map(d => (
          <KpiCard key={d.key} def={d} value={kpiValues[d.key] ?? 0} spark={kpiSparks[d.key] ?? []} trend={kpiTrends[d.key] ?? 0} />
        ))}
      </section>

      {/* ZONE BUSYNESS INDEX */}
      <section className={styles.zoneStrip}>
        <div className={styles.zoneStripHead}>
          <div><Activity size={14} color={C.blue} /><h2>Zone Busyness Index</h2></div>
          <div className={styles.legendRow}>
            <span><i style={{ background: C.emerald }} /> Free</span>
            <span><i style={{ background: C.orange }} /> Busy</span>
            <span><i style={{ background: C.red }} /> Congested</span>
          </div>
        </div>
        {warehouseEmpty ? (
          <div className={styles.seedState}>
            <strong>{firebaseConfigured ? "No warehouse data yet." : "Connect Firebase to begin."}</strong>
            <span>{firebaseConfigured ? "Seed the database to start tracking." : "Add NEXT_PUBLIC_FIREBASE_* values to .env.local."}</span>
            {firebaseConfigured && (
              <button type="button" className={styles.btnPrimary} onClick={() => void seed()} disabled={isSeeding}>
                {isSeeding ? "Seeding…" : "Seed Database"}
              </button>
            )}
          </div>
        ) : (
          <div className={styles.zoneGrid}>
            {state.zones.map(zone => {
              const busyness = getZoneBusyness(zone);
              const color = busynessColor(busyness);
              return (
                <div key={zone.id} className={styles.zoneCard}>
                  <div className={styles.zoneCardHead}>
                    <div><h3>{zone.name}</h3><small>({zone.aisleRange})</small></div>
                    <span className={styles.zonePct} style={{ color, borderColor: `${color}55` }}>{busyness}%</span>
                  </div>
                  <div className={styles.zoneTrack}>
                    <div style={{ width: `${busyness}%`, background: color }} />
                  </div>
                  <div className={styles.zoneCardFoot}>
                    <span>{zone.activeWorkers} pickers · {zone.activeTasks} tasks</span>
                    <strong style={{ color }}>{getBusynessLabel(busyness)}</strong>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* COMPARISON TOGGLE */}
      <div className={styles.compareBar}>
        <button type="button" className={`${styles.compareToggle} ${comparison ? styles.compareOn : ""}`}
          onClick={() => setComparison(c => !c)}>
          ⇄ Compare AI vs FIFO Routing
        </button>
        {comparison && <span className={styles.compareHint}>AI routing is selected for the live facility view.</span>}
      </div>

      {/* MAIN 3-COLUMN GRID */}
      <main className={styles.mainGrid}>
        {/* Left: Priority Queue */}
        <aside className={styles.panel}>
          <div className={styles.panelHead}><Target size={14} color={C.purple} /><span>AI Priority Queue</span></div>
          <div className={styles.queueList}>
            {warehouseEmpty ? (
              <p className={styles.panelEmpty}>No zone data available yet.</p>
            ) : (
              sortedZones.map((zone, idx) => <QueueCard key={zone.id} zone={zone} rank={idx} />)
            )}
          </div>
          <div className={styles.panelFoot}>Queue priorities update from zone task density.</div>
        </aside>

        {/* Center: Map */}
        <div className={styles.centerCol}>
          <WarehouseMap zones={state.zones} workers={mapWorkers} />
        </div>

        {/* Right: AI Decision Engine */}
        <aside className={styles.panel}>
          <div className={styles.panelHead}><Sparkles size={14} color={C.purple} /><span>AI Decision Engine</span></div>
          <DecisionEngine zone={busiestZone} />
        </aside>

        {/* Bottom Left: Agent Chat */}
        <div className={`${styles.panel} ${styles.bottomPanel}`}>
          <div className={styles.panelHead}><Radio size={14} color={C.blue} /><span>Agent Conversation</span></div>
          <AgentChat messages={chat} />
        </div>

        {/* Bottom Right: Analytics */}
        <div className={`${styles.panel} ${styles.bottomPanel}`}>
          <div className={styles.panelHead}><TrendingUp size={14} color={C.cyan} /><span>Live Analytics</span></div>
          <LiveAnalytics throughput={throughput} congestion={congestionSeries} />
        </div>
      </main>

      {/* Alerts */}
      <AlertStack alerts={alerts} onDismiss={dismissAlert} />

      {/* Footer */}
      <footer className={styles.pageFooter}>
        {state.meta.running ? "Live simulation writing updates" : "Simulation stopped"} · Tick {state.meta.simulationTick}
      </footer>
    </div>
  );
}
