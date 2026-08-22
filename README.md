<p align="center">
  <img src="assets/A2A_Digital_Twin_Poster.png" alt="A2A Digital Twin — Warehouse" width="100%">
</p>

<h1 align="center">A2A Digital Twin — Warehouse</h1>

<p align="center">
  <b>A simulated warehouse digital twin that replaces static FIFO queues with a dynamic, negotiated priority engine — coordinated by autonomous agents over A2A, with state accessed through an MCP-style tool layer.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776ab?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Next.js-16+-000000?logo=next.js&logoColor=white" alt="Next.js" />
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169e1?logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/Redis-7-dc382d?logo=redis&logoColor=white" alt="Redis" />
  <img src="https://img.shields.io/badge/Firebase-Firestore-ffca28?logo=firebase&logoColor=black" alt="Firebase" />
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License" />
</p>

<p align="center">Built by Team <a href="./CONTRIBUTORS.md"><b>Brute Force 6</b></a></p>

---

## Table of Contents

- [Problem](#problem)
- [Solution](#solution)
- [Architecture](#architecture)
- [Agents](#agents)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup](#setup)
- [Usage](#usage)
- [Validation Targets](#validation-targets)
- [Known Limitations & Future Scope](#known-limitations--future-scope)
- [License](#license)

---

## Problem

Quick-commerce dark stores run on fixed **FIFO order queues**. Every order is treated the same regardless of SLA risk, order value, item availability, or current picker load. A five-item order about to breach its SLA window waits behind nine single-item orders with hours of slack. The result: **avoidable SLA breaches, uneven picker utilization, and packing-stage bottlenecks** that a smarter scheduling policy could eliminate entirely.

## Solution

A2A Digital Twin is a **simulated warehouse orchestration platform** that replaces the static FIFO queue with a **dynamic priority engine**, driven by specialized agents that negotiate over which order gets worked next:

```mermaid
graph LR
    A[📦 Order Stream] --> B[Order Coordinator]
    B --> C[Dynamic Priority Queue]
    C --> D[Inventory Agent]
    C --> E[Picking Agent]
    C --> F[Packing & Dispatch Agent]
    D <-->|A2A Bus| E
    E <-->|A2A Bus| F
    D ---|MCP Tools| G[(PostgreSQL)]
    E ---|MCP Tools| G
    F ---|MCP Tools| G
    B --> H[🔥 Firebase Firestore]
    H --> I[📊 Live Dashboard]
```

1. **Orders arrive** through an ingestion API and are handed to the **Order Coordinator Agent**.
2. The Coordinator **scores and re-scores** orders continuously against a dynamic priority queue — factoring in SLA risk, inventory state, and current pick/pack load.
3. **Inventory**, **Picking**, and **Packing & Dispatch** agents negotiate task assignment over an **A2A message bus**, each exposing and consuming warehouse state through a standardized **MCP-style tool layer**.
4. Every state change streams to **Firebase Firestore**, powering a **real-time mission-control dashboard** with live KPIs, zone heatmaps, agent activity feeds, and animated worker tracking.
5. The same synthetic order stream can replay under **FIFO** and the **dynamic priority queue**, enabling direct policy comparison on identical workloads.

> **Note:** Scheduling logic is intentionally **pure rule-based** — no LLM sits in the decision path. An inert `explain_decision()` hook exists for a possible future commentary layer but plays no role in any actual decision today.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      FRONTEND (Next.js 16)                   │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐ │
│  │ KPI Cards   │  │ Warehouse Map│  │ Agent Chat / Alerts │ │
│  │ Zone Index  │  │ (SVG Canvas) │  │ Live Analytics      │ │
│  └──────┬──────┘  └──────┬───────┘  └──────────┬──────────┘ │
│         └────────────────┼─────────────────────┘            │
│                    🔥 Firestore Realtime Sync                │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────┼───────────────────────────────────┐
│                   BACKEND (FastAPI)                           │
│                          │                                    │
│  ┌───────────────────────┴───────────────────────────────┐   │
│  │               core/  (Framework Layer)                 │   │
│  │  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌───────────┐  │   │
│  │  │  A2A    │ │  MCP    │ │  Queue   │ │   Models  │  │   │
│  │  │  Bus    │ │Registry │ │  Engine  │ │  & Config │  │   │
│  │  └────┬────┘ └────┬────┘ └────┬─────┘ └───────────┘  │   │
│  └───────┼───────────┼──────────┼────────────────────────┘   │
│          │           │          │                              │
│  ┌───────┼───────────┼──────────┼────────────────────────┐   │
│  │       domains/warehouse/  (Business Logic)             │   │
│  │  ┌────┴────┐ ┌────┴────┐ ┌───┴──────┐ ┌───────────┐  │   │
│  │  │ Agents  │ │  MCP    │ │  Scorer  │ │Simulation │  │   │
│  │  │ (4+1)   │ │ Tools   │ │  Engine  │ │  Seeder   │  │   │
│  │  └────┬────┘ └────┬────┘ └────┬─────┘ └─────┬─────┘  │   │
│  └───────┼───────────┼──────────┼──────────────┼─────────┘   │
│          │           │          │              │               │
│     ┌────┴───────────┴──────────┴──────────────┴─────┐       │
│     │        PostgreSQL 16  ·  Redis 7               │       │
│     └────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────┘
```

## Agents

| Agent | Role | Key Responsibilities |
|---|---|---|
| 🎯 **Order Coordinator** | Orchestrator | Scores incoming orders, maintains the dynamic priority queue, delegates work to specialist agents |
| 📦 **Inventory Agent** | Stock Manager | Tracks stock levels and availability, answers reservation requests, triggers reorder alerts |
| 🏃 **Picking Agent** | Floor Operator | Claims and executes pick tasks, optimizes pick paths, reports utilization and load |
| 📤 **Packing & Dispatch** | Fulfillment | Finalizes orders for dispatch, manages packing stations, surfaces bottlenecks |
| 🚢 **Dock Agent** | _(Optional)_ | Manages dock doors and courier assignments — not required for primary MVP workflow |

## Key Features

- **🔄 Dynamic Priority Queue** — Orders scored and re-ranked in real-time based on SLA risk, inventory readiness, aisle congestion, and packing capacity
- **🤖 Multi-Agent Negotiation** — Autonomous agents communicate over A2A protocol, negotiating task assignment without central orchestration
- **🗺️ Interactive Warehouse Map** — Animated SVG floor plan with zone heatmaps, compartment labeling (A-1 through D-6), worker tracking, packing stations, and dispatch dock
- **📊 Real-Time Dashboard** — 9 live KPIs with sparkline trends, zone busyness index, throughput vs. FIFO comparison charts, and congestion analytics
- **💬 Agent Activity Feed** — Live chat-style feed showing inter-agent communications and decision rationale
- **🔥 Firebase Firestore Sync** — Bi-directional real-time state synchronization between backend simulation and frontend
- **🎮 Simulation Controls** — Start/stop simulation, seed database, and adjust simulation speed (1×/2×/4×) from the dashboard
- **🌗 Light/Dark Theme** — Full theme support with premium glassmorphism aesthetics
- **🔔 Alert System** — Real-time toast notifications for congestion events, SLA risks, and worker status changes

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend Framework** | FastAPI with async/await |
| **Agent Messaging** | Custom A2A protocol over Redis pub/sub |
| **State Access** | MCP-style tool registry |
| **Database** | PostgreSQL 16 (via SQLAlchemy + asyncpg) |
| **Cache & Pub/Sub** | Redis 7 |
| **Real-Time Sync** | Firebase Firestore |
| **Frontend** | Next.js 16 (Turbopack) + TypeScript |
| **Charting** | Recharts (Area, Line, Bar charts) |
| **Icons** | Lucide React |
| **Simulation** | Poisson-based synthetic order generator (seeded for reproducibility) |
| **Infrastructure** | Docker Compose |

## Project Structure

```
a2a-digital-twin/
├── backend/
│   ├── core/                          # Framework layer (domain-agnostic)
│   │   ├── a2a/                       #   Agent-to-Agent message bus & protocol
│   │   ├── agents/                    #   Base agent class
│   │   ├── api/                       #   Health check routes
│   │   ├── mcp/                       #   MCP tool registry
│   │   ├── models/                    #   Core data models (agent, message, task)
│   │   ├── queue_engine/              #   Base priority queue engine
│   │   ├── simulation/                #   Simulation framework
│   │   ├── config.py                  #   App settings (env-based)
│   │   ├── database.py               #   Async SQLAlchemy engine
│   │   └── main.py                    #   FastAPI app + lifespan
│   │
│   ├── domains/
│   │   └── warehouse/                 # Warehouse business logic
│   │       ├── agents/                #   Order, Inventory, Picking, Packing, Dock agents
│   │       ├── api/                   #   Warehouse-specific REST routes
│   │       ├── mcp/                   #   Warehouse MCP tools
│   │       ├── models/                #   Order, InventoryItem, Dock models
│   │       ├── queue_engine/          #   Dynamic priority scorer
│   │       ├── services/              #   Business logic services
│   │       └── simulation/            #   Order generator & database seeder
│   │
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── app/                       # Next.js app router
│   │   │   ├── page.tsx               #   Root page → DashboardView
│   │   │   ├── layout.tsx             #   Root layout
│   │   │   └── globals.css            #   Global styles
│   │   ├── core/                      # Shared frontend infrastructure
│   │   │   ├── api/                   #   API client utilities
│   │   │   ├── components/            #   Reusable UI components
│   │   │   ├── dashboard/             #   Dashboard framework
│   │   │   ├── hooks/                 #   Shared React hooks
│   │   │   ├── negotiation-viewer/    #   Agent negotiation visualizer
│   │   │   └── types/                 #   TypeScript type definitions
│   │   ├── domains/
│   │   │   └── warehouse/             # Warehouse-specific frontend
│   │   │       ├── views/             #   DashboardView (mission control)
│   │   │       ├── components/        #   WarehouseMap, QueueCard, KpiCard, etc.
│   │   │       ├── hooks/             #   useWarehouseTwin (Firestore sync)
│   │   │       ├── live-twin.ts       #   Computed state utilities
│   │   │       └── firestore-twin.ts  #   Firebase realtime listener
│   │   └── lib/
│   │       └── firebase.ts            #   Firebase app initialization
│   │
│   ├── package.json
│   ├── tsconfig.json
│   └── next.config.ts
│
├── docker-compose.yml                 # PostgreSQL 16 + Redis 7
├── .env.example                       # Environment template
├── CONTRIBUTORS.md
├── LICENSE
└── README.md
```

## Setup

### Prerequisites

- **Docker Desktop** (with WSL2 backend on Windows)
- **Python 3.12+**
- **Node.js 18+** and npm
- **Firebase project** (for Firestore real-time sync)

### 1. Clone the repository

```bash
git clone https://github.com/Maharshi-Paul/a2a-digital-twin.git
cd a2a-digital-twin
```

### 2. Start infrastructure

```bash
docker compose up -d
```

This starts **PostgreSQL 16** and **Redis 7** in containers. Verify with:

```bash
docker ps
# Should show wdt_postgres and wdt_redis both "Up"
```

### 3. Configure environment

Copy `.env.example` to `.env` at the project root:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `DOMAIN` | `warehouse` | Active domain |
| `DATABASE_URL` | `postgresql+asyncpg://wdt_user:wdt_pass@localhost:5432/warehouse_twin` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `QUEUE_TICK_SECONDS` | `2.0` | Priority queue re-score interval |
| `SIMULATION_SEED` | `42` | Reproducible simulation seed |
| `SIMULATION_LAMBDA` | `3.0` | Poisson arrival rate (orders/tick) |
| `LLM_PROVIDER` | `none` | LLM integration (unused in MVP) |

For the frontend, create `frontend/.env.local` with your Firebase credentials:

```env
NEXT_PUBLIC_FIREBASE_API_KEY=your_key
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=your_project.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=your_project_id
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=your_project.appspot.com
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=your_sender_id
NEXT_PUBLIC_FIREBASE_APP_ID=your_app_id
```

> **⚠️ Do not commit `.env` or `frontend/.env.local` — they contain secrets.**

### 4. Install dependencies

```bash
# Backend
pip install -r backend/requirements.txt

# Frontend
cd frontend && npm install
```

### 5. Start the backend

```bash
cd backend
uvicorn core.main:app --reload
```

On startup, this creates database tables, connects to Redis, and initializes all warehouse agents.

| Endpoint | URL |
|---|---|
| REST API | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/docs |
| WebSocket | ws://localhost:8000/ws/live |

### 6. Start the frontend

```bash
cd frontend
npm run dev
```

Dashboard available at **http://localhost:3000**.

### Windows Notes

- If Docker fails after installing WSL, **reboot first** before launching Docker Desktop.
- If PowerShell blocks scripts: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
- To stop everything: `Ctrl+C` in each terminal, then `docker compose down` from the project root.

## Usage

1. Open **http://localhost:3000** — the mission-control dashboard loads.
2. Click **DB** (Seed Database) to populate zones, SKUs, shelves, workers, and packing stations.
3. Click **Sim** (Start Simulation) to begin the synthetic order stream.
4. Watch in real-time:
   - **KPI strip** — 9 live metrics with sparkline trends and animated counters
   - **Zone Busyness Index** — per-zone congestion with color-coded severity
   - **Warehouse Map** — interactive SVG with shelf heatmaps, worker positions, packing stations, and dispatch dock
   - **Agent Chat** — live inter-agent communication feed
   - **Analytics** — throughput (AI vs FIFO), congestion, and SLA charts
   - **Priority Queue** — dynamically re-ranked zone cards
   - **AI Decision Engine** — real-time reasoning breakdown for the busiest zone
5. Use **speed controls** (1×/2×/4×) to accelerate simulation.
6. Toggle **dark/light theme** and **alerts** from the top navigation.

To **compare scheduling policies**, replay the same seed (`SIMULATION_SEED=42`) under FIFO and the dynamic queue, then diff the resulting metrics.

## Validation Targets

KPI improvements are only claimed once measured against the same workload — not asserted ahead of data:

| Metric | What It Measures |
|---|---|
| Average Waiting Time | Time from order ingestion to pick assignment |
| Throughput | Orders fulfilled per unit time |
| Picker Utilization | Worker active-time vs. idle-time ratio |
| SLA Breach Rate | Percentage of orders exceeding SLA window |
| Packing Bottleneck | Queue depth at packing stations |

## Known Limitations & Future Scope

| Current Limitation | Future Direction |
|---|---|
| Pure rule-based scoring (no ML/LLM) | Claude-based decision commentary layer via `explain_decision()` hook |
| Synthetic workloads only | Real-world order data integration |
| Single domain (warehouse) | Multi-domain support (airports, logistics hubs) |
| Dock agent is optional/unused | Full dock management with courier integration |
| No persistent user auth | Role-based access control for the dashboard |

## Contributors

See [CONTRIBUTORS.md](./CONTRIBUTORS.md) for the full team.

## License

MIT — see [LICENSE](./LICENSE).
