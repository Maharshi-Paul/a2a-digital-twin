"use client";

import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { useWebSocket } from "@/core/hooks/useWebSocket";
import { api } from "@/core/api/client";
import type { DecisionCommentary, QueueEntry, Zone, WorkerInfo, AgentLog } from "@/core/types";
import {
  Activity, Package, CheckCircle2, Users, Timer, AlertTriangle,
  TrendingUp, TrendingDown, Play, Square, Database, Sun, Moon,
  Sparkles, X, Radio, MapPin, Truck, Boxes, PackageCheck, Gauge,
  Target, Bot, Loader2
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

/* ============================== AGENT METADATA ============================== */
const AGENTS: Record<string, { name: string; color: string }> = {
  order_coordinator: { name: "Coordinator", color: C.blue },
  inventory: { name: "Inventory", color: C.cyan },
  picking: { name: "Picking", color: C.purple },
  packing: { name: "Packing", color: C.emerald },
  dock: { name: "Dispatch", color: C.orange },
  queue_engine: { name: "Queue Engine", color: C.purple },
};

/* ============================== MAP GEOMETRY ============================== */
const GRID_W = 1200, GRID_H = 620;
const SHELF_ROWS = 4, SHELF_COLS = 6;
const SHELF_W = 100, SHELF_H = 80;
const SHELF_AREA_LEFT = 90;
const SHELF_AREA_RIGHT = 680;
const SHELF_GAP_X = (SHELF_AREA_RIGHT - SHELF_COLS * SHELF_W) / (SHELF_COLS - 1);
const SHELF_AREA_TOP = 50;
const SHELF_AREA_BOTTOM = GRID_H - 50;
const SHELF_GAP_Y = (SHELF_AREA_BOTTOM - SHELF_AREA_TOP - SHELF_ROWS * SHELF_H) / (SHELF_ROWS - 1);
const ZONE_LABELS = ["A", "B", "C", "D"];
const ZONE_COLORS = ["#3b82f6", "#a855f7", "#f97316", "#22d3ee"];

const OPS_LEFT = SHELF_AREA_LEFT + SHELF_AREA_RIGHT + 50;
const PACK_W = 110, PACK_H = 80, PACK_GAP = 20;
const DISPATCH_LEFT = OPS_LEFT + PACK_W + 40;
const DISPATCH_W = 80, DISPATCH_H = 240;

function shelfPos(r: number, c: number) {
  return {
    x: SHELF_AREA_LEFT + c * (SHELF_W + SHELF_GAP_X),
    y: SHELF_AREA_TOP + r * (SHELF_H + SHELF_GAP_Y),
  };
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function busynessColor(pct: number) {
  if (pct >= 70) return C.red;
  if (pct >= 40) return C.orange;
  return C.emerald;
}

function getBusynessLabel(percent: number): "Free" | "Busy" | "Congested" {
  if (percent >= 70) return "Congested";
  if (percent >= 40) return "Busy";
  return "Free";
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
      const p = clamp((now - start) / 600, 0, 1);
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
  const decimals = def.unit === "%" ? 1 : def.key === "avgScore" ? 4 : 0;
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
              fill={`url(#grad-${def.key})`} isAnimationActive={false} dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/* ============================== WAREHOUSE MAP ============================== */
function WarehouseMap({ zones, workers }: { zones: Zone[]; workers: WorkerInfo[] }) {
  const [zoom, setZoom] = useState(1);
  const [hover, setHover] = useState<{ id: number; zone: string; col: number; congestion: number } | null>(null);

  const shelves = useMemo(() => {
    return Array.from({ length: SHELF_ROWS * SHELF_COLS }, (_, i) => {
      const r = Math.floor(i / SHELF_COLS), c = i % SHELF_COLS;
      const { x, y } = shelfPos(r, c);
      const zoneIdx = Math.min(r, Math.max(0, zones.length - 1));
      const zone = zones[zoneIdx];
      const congestion = zone ? zone.congestion : 0.15;
      const jitter = ((i % 3) - 1) * 0.04;
      const zoneLabel = ZONE_LABELS[r] ?? ZONE_LABELS[ZONE_LABELS.length - 1];
      return { id: i, x, y, zone: zoneLabel, col: c + 1, congestion: clamp(congestion + jitter, 0.05, 0.95) };
    });
  }, [zones]);

  const packStations = [0, 1, 2].map(i => {
    const totalH = 3 * PACK_H + 2 * PACK_GAP;
    const startY = (GRID_H - totalH) / 2;
    return { x: OPS_LEFT, y: startY + i * (PACK_H + PACK_GAP), label: `PACK ${i + 1}` };
  });

  const dockY = (GRID_H - DISPATCH_H) / 2;

  const coloredWorkers = useMemo(() => {
    const palette = [C.cyan, C.purple, C.emerald, C.orange, C.blue, "#f472b6"];
    return workers.map((w, idx) => ({
      ...w,
      color: palette[idx % palette.length],
      normX: clamp(w.pos?.[0] ?? (20 + idx * 7), 5, 95),
      normY: clamp(w.pos?.[1] ?? (20 + idx * 6), 5, 95),
    }));
  }, [workers]);

  return (
    <div className={styles.mapWrap}>
      <div className={styles.mapToolbar}>
        <MapPin size={14} />
        <span>Facility 04 · Zone A–D (Floorplan View)</span>
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

          {/* Zone row labels & separators */}
          {ZONE_LABELS.map((label, r) => {
            const rowY = SHELF_AREA_TOP + r * (SHELF_H + SHELF_GAP_Y);
            const zoneColor = ZONE_COLORS[r];
            return (
              <g key={label}>
                <rect x={8} y={rowY + SHELF_H / 2 - 16} width={64} height={32} rx={8}
                  fill={`${zoneColor}18`} stroke={zoneColor} strokeOpacity={0.4} strokeWidth={1.2} />
                <text x={40} y={rowY + SHELF_H / 2 + 5} textAnchor="middle"
                  fill={zoneColor} fontSize="14" fontWeight="700" letterSpacing="0.06em">
                  Zone {label}
                </text>
                {r < SHELF_ROWS - 1 && (
                  <line x1={SHELF_AREA_LEFT} y1={rowY + SHELF_H + SHELF_GAP_Y / 2}
                    x2={SHELF_AREA_LEFT + SHELF_AREA_RIGHT} y2={rowY + SHELF_H + SHELF_GAP_Y / 2}
                    stroke={zoneColor} strokeOpacity={0.15} strokeWidth={1} strokeDasharray="6 4" />
                )}
              </g>
            );
          })}

          {/* OPS separator */}
          <line x1={OPS_LEFT - 25} y1={30} x2={OPS_LEFT - 25} y2={GRID_H - 30}
            stroke="rgba(255,255,255,0.08)" strokeWidth={1} strokeDasharray="4 6" />
          <text x={OPS_LEFT - 25} y={22} textAnchor="middle" fill="rgba(255,255,255,0.3)" fontSize="11" fontWeight="600">
            OPS →
          </text>

          {/* Shelves */}
          {shelves.map(s => {
            const color = busynessColor(s.congestion * 100);
            const compartmentId = `${s.zone}-${s.col}`;
            return (
              <g key={s.id} onMouseEnter={() => setHover(s)} onMouseLeave={() => setHover(null)} style={{ cursor: "pointer" }}>
                <rect x={s.x} y={s.y} width={SHELF_W} height={SHELF_H} rx={8}
                  fill="rgba(255,255,255,0.045)" stroke={color} strokeOpacity={0.55}
                  strokeWidth={hover?.id === s.id ? 2.5 : 1.2}
                  style={{ filter: hover?.id === s.id ? "url(#glowSoft)" : "none", transition: "stroke .6s ease" }} />
                <rect x={s.x + 4} y={s.y + SHELF_H - 8} width={SHELF_W - 8} height={4} rx={2} fill={color} opacity={0.8} />
                <text x={s.x + SHELF_W / 2} y={s.y + 22} textAnchor="middle"
                  fill="rgba(255,255,255,0.7)" fontSize="14" fontWeight="700">{compartmentId}</text>
                <text x={s.x + SHELF_W / 2} y={s.y + 42} textAnchor="middle"
                  fill={color} fontSize="12" fontWeight="600">{Math.round(s.congestion * 100)}%</text>
                <circle cx={s.x + SHELF_W / 2} cy={s.y + 58} r={4} fill={color} opacity={0.65} />
              </g>
            );
          })}

          {/* Packing stations */}
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

          {/* Dispatch dock */}
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

          {/* Workers */}
          {coloredWorkers.map(w => (
            <g key={w.id} style={{ transform: `translate(${w.normX * GRID_W / 100}px, ${w.normY * GRID_H / 100}px)`, transition: "transform 1.4s ease" }}>
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
            <span>Live Congestion</span>
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
function QueueCard({ order, rank }: { order: QueueEntry; rank: number }) {
  const scorePct = Math.round(clamp(order.score * 100, 5, 100));
  const critical = order.sla_risk > 0.7;
  const color = critical ? C.red : order.sla_risk > 0.4 ? C.orange : C.emerald;

  return (
    <div className={`${styles.queueCard} ${critical ? styles.critical : ""}`}>
      <div className={styles.qcRing}>
        <svg viewBox="0 0 36 36">
          <circle cx="18" cy="18" r="15.5" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="3" />
          <circle cx="18" cy="18" r="15.5" fill="none" stroke={color}
            strokeWidth="3" strokeDasharray={`${scorePct} 100`} strokeLinecap="round" transform="rotate(-90 18 18)"
            style={{ transition: "stroke-dasharray 0.8s ease" }} />
        </svg>
        <span>#{rank + 1}</span>
      </div>
      <div className={styles.qcBody}>
        <div className={styles.qcTop}>
          <span className={styles.qcId}>{order.external_id}</span>
          <span className={`${styles.qcBadge} ${critical ? styles.bRed : order.sla_risk > 0.4 ? styles.bOrange : styles.bBlue}`}>
            Score: {order.score.toFixed(4)}
          </span>
        </div>
        <div className={styles.qcMeta}>
          <span>SLA Risk: {Math.round(order.sla_risk * 100)}%</span>
          <span>·</span>
          <span>Order ID: {order.order_id}</span>
        </div>
      </div>
    </div>
  );
}

/* ============================== AI DECISION ENGINE ============================== */
function DecisionEngine({ topOrder, commentary }: { topOrder?: QueueEntry; commentary?: DecisionCommentary }) {
  if (!topOrder) {
    return (
      <div className={styles.decisionPanel}>
        <p className={styles.panelEmpty}>
          Waiting for active orders. Click <b>DB</b> to seed warehouse data, then <b>Sim</b> to start the order generator.
        </p>
      </div>
    );
  }

  const reasons = [
    { text: `SLA Risk at ${Math.round(topOrder.sla_risk * 100)}% urgency weight`, ok: topOrder.sla_risk < 0.7 },
    { text: `Total A2A score: ${topOrder.score.toFixed(4)}`, ok: true },
    { text: "Inventory readiness verified across zones", ok: true },
    { text: "Pick path & packing station balanced", ok: true },
  ];

  return (
    <div className={styles.decisionPanel}>
      <div className={styles.decisionHead}>
        <Sparkles size={15} color={C.purple} />
        <span>Prioritizing <b>{topOrder.external_id}</b> (Rank #1)</span>
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
        <span>Assigned Priority Score</span>
        <b>{topOrder.score.toFixed(4)}</b>
      </div>
      {commentary && (
        <div
          style={{
            marginTop: 10,
            padding: "8px 10px",
            borderRadius: 8,
            background: "rgba(168, 85, 247, 0.08)",
            border: "1px solid rgba(168, 85, 247, 0.25)",
            fontSize: 11,
            lineHeight: 1.45,
            color: "rgba(255,255,255,0.9)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              marginBottom: 4,
              fontSize: 9,
              fontWeight: 700,
              letterSpacing: "0.06em",
              textTransform: "uppercase" as const,
              color: C.purple,
            }}
          >
            <Bot size={10} /> AI Rationale · {commentary.external_id}
          </div>
          {commentary.commentary}
        </div>
      )}
    </div>
  );
}

/* ============================== AGENT CHAT ============================== */
function AgentChat({ logs }: { logs: AgentLog[] }) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs.length]);

  return (
    <div className={styles.chatPanel}>
      <div className={styles.chatAgents}>
        {Object.entries(AGENTS).map(([key, a]) => (
          <div key={key} className={styles.chatAgentChip}>
            <span className={styles.dotOnline} style={{ background: a.color }} />
            {a.name}
          </div>
        ))}
      </div>
      <div className={styles.chatBody}>
        {logs.length === 0 ? (
          <p className={styles.panelEmpty} style={{ padding: 16 }}>
            A2A Message Bus connected to Redis. Inter-agent messages will appear in real time when simulation runs.
          </p>
        ) : (
          logs.map((m) => {
            const agentMeta = AGENTS[m.sender] ?? { name: m.sender, color: C.blue };
            return (
              <div key={m.id} className={styles.chatBubbleRow}>
                <div className={styles.chatAvatar} style={{ background: `${agentMeta.color}22`, color: agentMeta.color, borderColor: `${agentMeta.color}55` }}>
                  {agentMeta.name[0]}
                </div>
                <div className={styles.chatBubble} style={{ borderColor: `${agentMeta.color}33` }}>
                  <div className={styles.chatName} style={{ color: agentMeta.color }}>
                    {agentMeta.name} → {m.receiver} <small style={{ color: C.textDim, marginLeft: 6 }}>{m.type}</small>
                  </div>
                  <div>
                    {m.payload ? JSON.stringify(m.payload) : "Message dispatched over A2A bus"}
                  </div>
                </div>
              </div>
            );
          })
        )}
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

/* ============================== MAIN DASHBOARD ============================== */
export function DashboardView() {
  const [theme, setTheme] = useState<"light" | "dark">("dark");
  const [now, setNow] = useState(new Date());
  const [speed, setSpeed] = useState(1);
  const [comparison, setComparison] = useState(false);
  const [mounted, setMounted] = useState(false);

  const [isSeeding, setIsSeeding] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [simRunning, setSimRunning] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => { setMounted(true); }, []);
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  // WebSocket data directly from backend FastAPI /ws/live
  const { data, connected, isWakingUp, connectionError, commentaries } = useWebSocket();
  const latestCommentary = commentaries.length > 0 ? commentaries[commentaries.length - 1] : undefined;

  // Sync simulation running state on connection
  useEffect(() => {
    if (connected) {
      api.simulation.status()
        .then((res) => {
          if (typeof res?.running === "boolean") {
            setSimRunning(res.running);
          }
        })
        .catch(() => {});
    }
  }, [connected]);

  // Seed DB action
  const handleSeed = useCallback(async () => {
    setIsSeeding(true);
    setActionError(null);
    try {
      await api.simulation.seed();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to seed database.");
    } finally {
      setIsSeeding(false);
    }
  }, []);

  // Start simulation action
  const handleStart = useCallback(async () => {
    setIsStarting(true);
    setActionError(null);
    try {
      await api.simulation.start();
      setSimRunning(true);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to start simulation.");
    } finally {
      setIsStarting(false);
    }
  }, []);

  // Stop simulation action
  const handleStop = useCallback(async () => {
    setActionError(null);
    try {
      await api.simulation.stop();
      setSimRunning(false);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to stop simulation.");
    }
  }, []);

  // Real backend KPIs
  const totalOrders = data?.kpis?.orders?.total ?? 0;
  const pendingOrders = (data?.kpis?.orders?.by_status?.["PENDING"] ?? 0) + (data?.kpis?.orders?.by_status?.["QUEUED"] ?? 0);
  const processingOrders = data?.kpis?.orders?.by_status?.["PROCESSING"] ?? 0;
  const completedOrders = data?.kpis?.orders?.by_status?.["COMPLETED"] ?? 0;
  const slaBreaches = data?.kpis?.sla_breached_count ?? 0;
  const avgScore = data?.kpis?.avg_priority_score ?? 0;
  const workerUtil = Math.round((data?.kpis?.worker_utilization ?? 0) * 100);
  const zoneCongestion = Math.round((data?.kpis?.avg_zone_congestion ?? 0) * 100);
  const activeWorkers = data?.warehouse?.workers?.filter(w => w.status === "ACTIVE" || w.status === "BUSY").length ?? data?.warehouse?.workers?.length ?? 0;

  const KPI_DEFS: KpiDef[] = [
    { key: "totalOrders", label: "Total Orders", icon: Package, color: C.blue, unit: "" },
    { key: "pendingOrders", label: "Pending Queue", icon: Timer, color: C.orange, unit: "" },
    { key: "processingOrders", label: "In Processing", icon: Activity, color: C.purple, unit: "" },
    { key: "completedOrders", label: "Completed Orders", icon: CheckCircle2, color: C.emerald, unit: "" },
    { key: "slaBreaches", label: "SLA Breaches", icon: AlertTriangle, color: C.red, unit: "" },
    { key: "avgScore", label: "Avg Priority Score", icon: Gauge, color: C.cyan, unit: "" },
    { key: "zoneCongestion", label: "Avg Congestion", icon: AlertTriangle, color: C.orange, unit: "%" },
    { key: "workerUtil", label: "Worker Utilization", icon: Users, color: C.emerald, unit: "%" },
    { key: "activeWorkers", label: "Active Pickers", icon: Truck, color: C.blue, unit: "" },
  ];

  const kpiValues: Record<string, number> = {
    totalOrders,
    pendingOrders,
    processingOrders,
    completedOrders,
    slaBreaches,
    avgScore,
    zoneCongestion,
    workerUtil,
    activeWorkers,
  };

  const [kpiSparks, setKpiSparks] = useState<Record<string, { i: number; v: number }[]>>(() =>
    Object.fromEntries(KPI_DEFS.map(d => [d.key, Array.from({ length: 16 }, (_, i) => ({ i, v: 20 + Math.random() * 30 }))]))
  );

  useEffect(() => {
    if (!data) return;
    setKpiSparks(prev => {
      const next: Record<string, { i: number; v: number }[]> = {};
      for (const d of KPI_DEFS) {
        const arr = prev[d.key] ?? [];
        const v = kpiValues[d.key] ?? 0;
        next[d.key] = [...arr.slice(-15), { i: (arr.at(-1)?.i ?? 0) + 1, v: Math.max(0, v) }];
      }
      return next;
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data?.timestamp]);

  const zones: Zone[] = data?.warehouse?.zones ?? [];
  const workers: WorkerInfo[] = data?.warehouse?.workers ?? [];
  const queueOrders: QueueEntry[] = data?.queue ?? [];
  const agentLogs: AgentLog[] = data?.agent_logs ?? [];
  const topOrder = queueOrders.length > 0 ? queueOrders[0] : undefined;

  const [throughput] = useState([
    { t: "1m", ai: 68, fifo: 42 },
    { t: "2m", ai: 72, fifo: 44 },
    { t: "3m", ai: 76, fifo: 46 },
    { t: "4m", ai: 81, fifo: 48 },
    { t: "5m", ai: 85, fifo: 49 },
    { t: "6m", ai: 89, fifo: 50 },
  ]);

  const [congestionSeries] = useState([
    { t: "1m", v: 24 },
    { t: "2m", v: 38 },
    { t: "3m", v: 45 },
    { t: "4m", v: 32 },
    { t: "5m", v: 28 },
    { t: "6m", v: 22 },
  ]);

  return (
    <div className={styles.twinRoot}>
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
            <div className={styles.tnSub}>A2A Multi-Agent Mission Control</div>
          </div>
          <div className={`${styles.livePill} ${connected ? styles.liveConnected : isWakingUp ? styles.liveWaking : ""}`}>
            <span className={styles.liveDot} />
            {connected ? "LIVE (A2A WEBSOCKET)" : isWakingUp ? "WAKING UP BACKEND…" : "CONNECTING…"}
          </div>
        </div>
        <div className={styles.tnCenter}>
          <div className={styles.clock}>{mounted ? now.toLocaleTimeString([], { hour12: false }) : "--:--:--"}</div>
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
          <button type="button" className={styles.btnGhost} onClick={() => void handleSeed()} disabled={isSeeding || !connected}>
            <Database size={14} />{isSeeding ? "Seeding…" : "DB"}
          </button>
          {simRunning ? (
            <button type="button" className={styles.btnDanger} onClick={() => void handleStop()}>
              <Square size={14} />Stop
            </button>
          ) : (
            <button type="button" className={styles.btnPrimary} onClick={() => void handleStart()} disabled={isStarting || !connected}>
              <Play size={14} />{isStarting ? "Starting…" : "Sim"}
            </button>
          )}
        </div>
      </header>

      {/* Cold start waking notice */}
      {isWakingUp && (
        <div className={`${styles.notice} ${styles.noticeWake}`} role="status">
          <Loader2 size={16} className="animate-spin" />
          <span><strong>Backend waking up:</strong> Initializing PostgreSQL, Redis pub/sub bus, and 5 A2A agents (free-tier cold start, ~30–50s). Please wait...</span>
        </div>
      )}

      {/* Connection error notice */}
      {connectionError && !isWakingUp && (
        <div className={styles.notice} role="alert">
          <AlertTriangle size={14} />
          <span><strong>Connection note:</strong> {connectionError}. Retrying in background...</span>
        </div>
      )}

      {/* Action error notice */}
      {actionError && (
        <div className={styles.notice} role="alert">
          <AlertTriangle size={14} />
          <span><strong>Action error:</strong> {actionError}</span>
        </div>
      )}

      {/* KPI STRIP */}
      <section className={styles.kpiStrip}>
        {KPI_DEFS.map(d => (
          <KpiCard key={d.key} def={d} value={kpiValues[d.key] ?? 0} spark={kpiSparks[d.key] ?? []} trend={0} />
        ))}
      </section>

      {/* ZONE BUSYNESS INDEX */}
      <section className={styles.zoneStrip}>
        <div className={styles.zoneStripHead}>
          <div><Activity size={14} color={C.blue} /><h2>Zone Busyness Index (PostgreSQL)</h2></div>
          <div className={styles.legendRow}>
            <span><i style={{ background: C.emerald }} /> Free</span>
            <span><i style={{ background: C.orange }} /> Busy</span>
            <span><i style={{ background: C.red }} /> Congested</span>
          </div>
        </div>
        {zones.length === 0 ? (
          <div className={styles.seedState}>
            <strong>{connected ? "No zones loaded yet." : "Connecting to backend..."}</strong>
            <span>{connected ? "Click 'DB' to seed warehouse items and zones." : "Waiting for WebSocket connection to open."}</span>
            {connected && (
              <button type="button" className={styles.btnPrimary} onClick={() => void handleSeed()} disabled={isSeeding}>
                {isSeeding ? "Seeding…" : "Seed Database"}
              </button>
            )}
          </div>
        ) : (
          <div className={styles.zoneGrid}>
            {zones.map(zone => {
              const busyness = Math.round(zone.congestion * 100);
              const color = busynessColor(busyness);
              return (
                <div key={zone.id} className={styles.zoneCard}>
                  <div className={styles.zoneCardHead}>
                    <div><h3>{zone.name}</h3><small>Zone #{zone.id}</small></div>
                    <span className={styles.zonePct} style={{ color, borderColor: `${color}55` }}>{busyness}%</span>
                  </div>
                  <div className={styles.zoneTrack}>
                    <div style={{ width: `${busyness}%`, background: color }} />
                  </div>
                  <div className={styles.zoneCardFoot}>
                    <span>Live Congestion: {busyness}%</span>
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
        {comparison && <span className={styles.compareHint}>A2A Multi-Factor priority negotiation active.</span>}
      </div>

      {/* MAIN 3-COLUMN GRID */}
      <main className={styles.mainGrid}>
        {/* Left: Priority Queue */}
        <aside className={styles.panel}>
          <div className={styles.panelHead}><Target size={14} color={C.purple} /><span>A2A Priority Queue</span></div>
          <div className={styles.queueList}>
            {queueOrders.length === 0 ? (
              <p className={styles.panelEmpty}>
                {simRunning ? "Calculating dynamic priority scores..." : "No orders in queue. Click 'Seed DB' and 'Sim' to generate orders."}
              </p>
            ) : (
              queueOrders.slice(0, 15).map((order, idx) => (
                <QueueCard key={order.order_id} order={order} rank={idx} />
              ))
            )}
          </div>
          <div className={styles.panelFoot}>Priority scores calculated every tick via 5-factor A2A engine.</div>
        </aside>

        {/* Center: Map */}
        <div className={styles.centerCol}>
          <WarehouseMap zones={zones} workers={workers} />
        </div>

        {/* Right: AI Decision Engine */}
        <aside className={styles.panel}>
          <div className={styles.panelHead}><Sparkles size={14} color={C.purple} /><span>AI Decision Engine</span></div>
          <DecisionEngine topOrder={topOrder} commentary={latestCommentary} />
        </aside>

        {/* Bottom Left: Agent Chat */}
        <div className={`${styles.panel} ${styles.bottomPanel}`}>
          <div className={styles.panelHead}><Radio size={14} color={C.blue} /><span>Agent Conversation (A2A Message Bus)</span></div>
          <AgentChat logs={agentLogs} />
        </div>

        {/* Bottom Right: Analytics */}
        <div className={`${styles.panel} ${styles.bottomPanel}`}>
          <div className={styles.panelHead}><TrendingUp size={14} color={C.cyan} /><span>Live Analytics</span></div>
          <LiveAnalytics throughput={throughput} congestion={congestionSeries} />
        </div>
      </main>

      {/* Footer */}
      <footer className={styles.pageFooter}>
        {simRunning ? "Live simulation active" : "Simulation stopped"} · Backend: {connected ? "Connected" : "Disconnected"}
      </footer>
    </div>
  );
}
