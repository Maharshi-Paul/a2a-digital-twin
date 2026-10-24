<p align="center">
  <img src="assets/A2A_Digital_Twin_Poster.png" alt="A2A Digital Twin — Warehouse" width="100%">
</p>

<h1 align="center">A2A Digital Twin — Warehouse</h1>

<p align="center">
  <b>A simulated warehouse digital twin that replaces static FIFO queues with a dynamic, negotiated priority engine. Autonomous agents coordinate over A2A, and all state access goes through an MCP-style tool layer.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776ab?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Next.js-16.3-000000?logo=next.js&logoColor=white" alt="Next.js" />
  <img src="https://img.shields.io/badge/PostgreSQL-16%20%7C%20Neon-4169e1?logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/Redis-7%20%7C%20Upstash-dc382d?logo=redis&logoColor=white" alt="Redis" />
  <img src="https://img.shields.io/badge/Gemini_API-2.5--flash--lite%20(optional)-8e75b2?logo=googlegemini&logoColor=white" alt="Gemini API" />
  <img src="https://img.shields.io/badge/Docker-Ready-2496ed?logo=docker&logoColor=white" alt="Docker" />
  <img src="https://img.shields.io/badge/Vercel-Deployed-000000?logo=vercel&logoColor=white" alt="Vercel" />
  <img src="https://img.shields.io/badge/Render-Deployed-46e3b7?logo=render&logoColor=black" alt="Render" />
  <img src="https://img.shields.io/badge/Tests-14%20Passed-brightgreen?logo=pytest&logoColor=white" alt="Tests" />
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License" />
</p>

<p align="center">Built by Team <a href="./CONTRIBUTORS.md"><b>Brute Force 6</b></a></p>

---

## Table of Contents

- [Quick Start](#quick-start)
- [Problem](#problem)
- [Solution](#solution)
- [Priority Scoring Formula](#priority-scoring-formula)
- [Architecture](#architecture)
- [Agents & MCP Tools](#agents--mcp-tools)
- [Key Features](#key-features)
- [Optional LLM-Assisted Features](#optional-llm-assisted-features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup & Local Development](#setup--local-development)
- [Testing & Quality Assurance](#testing--quality-assurance)
- [REST API & WebSocket Reference](#rest-api--websocket-reference)
- [Production Cloud Deployment Guide](#production-cloud-deployment-guide)
- [Usage Guide](#usage-guide)
- [Validation Targets](#validation-targets)
- [Known Limitations & Roadmap](#known-limitations--roadmap)
- [Contributors](#contributors)
- [License](#license)

---

## Quick Start

Requires Python 3.11+, Node.js 20.9+, and Docker. The full walkthrough is in [Setup & Local Development](#setup--local-development).

```bash
git clone https://github.com/Maharshi-Paul/a2a-digital-twin.git
cd a2a-digital-twin
cp .env.example .env

docker compose up -d                     # local PostgreSQL 16 + Redis 7
pip install -r backend/requirements.txt
cd backend && python -m uvicorn core.main:app --reload --port 8000
```

In a second terminal:

```bash
cd frontend && npm install && npm run dev
```

Open [http://localhost:3000](http://localhost:3000), click **Seed DB**, then **Start Sim**.

---

## Problem

Quick-commerce dark stores and micro-fulfillment centers operate under strict SLA windows (for example, 10–30 minute deliveries). Yet conventional facilities rely on fixed **FIFO (First-In, First-Out) order queues**, and under FIFO:

- High-value orders close to breaching their SLA get stranded behind low-priority single-item orders with hours of slack.
- Pickers crowd the same aisles at the same time, creating physical bottlenecks on the floor.
- Work is released to picking without regard for packing-station availability, causing gridlock in the staging area.

The result is **avoidable SLA penalties, uneven worker utilization, and fulfillment delays** that a state-aware dispatch system can prevent.

---

## Solution

**A2A Digital Twin** is an agentic, queue-aware warehouse simulation and orchestration platform. It replaces static FIFO dispatching with a **dynamic priority engine** run by autonomous specialist agents. The agents communicate over an **Agent-to-Agent (A2A)** message bus and read and update warehouse state through a standardized **MCP (Model Context Protocol)** tool layer.

```mermaid
graph LR
    A[📦 Synthetic Order Stream] --> B[Order Coordinator]
    B --> C[Dynamic Priority Engine]
    C --> D[Inventory Agent]
    C --> E[Picking Agent]
    C --> F[Packing & Dispatch Agent]
    C --> J[Dock Agent]
    D <-->|A2A Bus - Redis Pub/Sub| E
    E <-->|A2A Bus - Redis Pub/Sub| F
    F <-->|A2A Bus - Redis Pub/Sub| J
    D ---|MCP Tools| G[(Neon / PostgreSQL 16)]
    E ---|MCP Tools| G
    F ---|MCP Tools| G
    J ---|MCP Tools| G
    B -->|Native WebSocket ws://| H[📊 Live Next.js 16 Dashboard]
    B -.->|Optional Sync| I[🔥 Firebase Firestore]
```

### End-to-End Orchestration Flow

1. **Order ingestion.** Poisson-distributed synthetic orders enter through the API and are registered by the **Order Coordinator Agent**.
2. **Dynamic priority scoring.** Orders are continually scored and re-ranked with a 5-factor model covering SLA urgency, wait time, inventory readiness, aisle congestion, and packing capacity.
3. **Multi-agent negotiation.** The specialist agents (**Inventory**, **Picking**, **Packing & Dispatch**, and **Dock**) negotiate assignments over the **A2A Redis message bus**.
4. **Standardized state access.** State reads and status changes go through decoupled **MCP tools** backed by an async SQLAlchemy database layer.
5. **Real-time telemetry.** State is broadcast over a native **WebSocket channel** (`/ws/live`) with a 25-second heartbeat and cold-start health probes, feeding the **Next.js 16 Mission Control Dashboard**.
6. **Policy benchmarking.** Synthetic workloads can be replayed deterministically across a **FIFO baseline**, **rule-based dynamic priority**, and **LLM-assisted batch re-ranking** for side-by-side comparison.

> [!NOTE]
> **Data authenticity and no lock-in**
> - **Backend-computed state:** Priority scores, SLA countdowns, aisle congestion metrics, and inter-agent dialogues are all calculated by the FastAPI backend and broadcast over native WebSockets and REST.
> - **Facility canvas:** The 2D SVG floorplan maps real PostgreSQL shelf inventory and worker coordinates onto an interactive canvas.
> - **No Firebase dependency:** The app runs entirely on WebSockets and REST endpoints. Firebase Firestore sync is optional and disabled by default.

---

## Priority Scoring Formula

The dynamic priority engine scores every pending order on each tick with a weighted multi-factor function:

$$\text{Priority Score} = w_1 \cdot \text{SLA\_Risk} + w_2 \cdot \text{Wait\_Time} + w_3 \cdot \text{Inv\_Readiness} + w_4 \cdot \text{Congestion\_Factor} + w_5 \cdot \text{Packing\_Factor}$$

| Factor | Weight | Formula / Definition | Objective |
|---|---|---|---|
| **SLA Risk** | $w_1 = 0.35$ | $\max\left(0, 1 - \frac{\text{minutes\_remaining}}{\text{max\_sla\_window}}\right)$ | Expedite orders approaching SLA breach |
| **Wait Time** | $w_2 = 0.15$ | $\min\left(1, \frac{\text{elapsed\_wait\_minutes}}{\text{max\_wait\_window}}\right)$ | Prevent queue starvation for older orders |
| **Inventory Readiness** | $w_3 = 0.25$ | $\frac{\sum \text{available items in stock}}{\text{total order items requested}}$ | Prioritize orders that are ready to pick immediately |
| **Aisle Congestion** | $w_4 = 0.10$ | $1.0 - \text{average congestion of target zones}$ | Route pickers away from crowded aisles |
| **Packing Capacity** | $w_5 = 0.15$ | $1.0 - \text{overall packing station utilization}$ | Throttle picking when packing tables are full |

The weights sum to $1.00$ and can be overridden with the environment variables `W_SLA_RISK`, `W_WAIT_TIME`, `W_INVENTORY_READINESS`, `W_AISLE_CONGESTION`, and `W_PACKING_CAPACITY`.

---

## Architecture

```mermaid
graph TB
    subgraph FE["FRONTEND — Next.js 16 (App Router + Turbopack)"]
        KPI["9 Live KPI Cards<br/>Sparkline Trends"]
        MAP["Interactive SVG Floorplan<br/>Shelf Heatmap & Workers"]
        CHAT["Agent Dialogue Stream<br/>Live Decision Traces"]
        CTRL["Simulation Controls<br/>Speed: 1x / 2x / 4x"]
    end

    SYNC(["🔌 Native WebSocket (/ws/live)  ·  REST API (/api)  ·  🔥 Optional Firestore"])

    subgraph BE["BACKEND — FastAPI (Python 3.11+)"]
        subgraph CORE["core/ — Framework Layer"]
            A2A["A2A Message Bus<br/>(Redis Pub/Sub)"]
            MCPR["MCP Tool Registry<br/>(Decoupled State Access)"]
            QE["Queue Engine<br/>(Dynamic Scorer & FIFO)"]
            DB_ENG["Dual Database Engine<br/>Pooled + Unpooled DDL"]
        end

        subgraph DOMAIN["domains/warehouse/ — Domain Logic"]
            AGENTS["Autonomous Agents<br/>Order, Inventory, Picking, Packing, Dock"]
            MCPT["Warehouse MCP Tools<br/>(SKU, Zones, Workers, Docks)"]
            SCORER["Multi-Factor Scorer"]
            SIM["Poisson Order Generator<br/>& Database Seeder"]
            LLM["LLM Re-Ranker & Commentary<br/><i>(Optional Gemini 2.5)</i>"]
        end
    end

    subgraph DATA["DATA & INFRASTRUCTURE"]
        PG[("Neon Serverless PostgreSQL 16<br/>(PgBouncer Pooled + Direct DDL)")]
        RD[("Redis 7 / Upstash Redis<br/>(rediss:// TLS Support)")]
    end

    FE <--> SYNC
    SYNC <--> BE
    QE --> SCORER
    QE -.optional.-> LLM
    A2A <--> AGENTS
    MCPR <--> MCPT
    MCPT <--> DB_ENG
    DB_ENG <--> PG
    A2A <--> RD
```

---

## Agents & MCP Tools

### Autonomous Specialist Agents

| Agent | Responsibility | Key Interactions |
|---|---|---|
| 🎯 **Order Coordinator** | Orchestrator & dispatcher | Ingests incoming orders, triggers periodic queue scoring, negotiates task assignments, streams live traces |
| 📦 **Inventory Agent** | Stock & replenishment | Audits SKU availability across shelves (A-1 to D-6), reserves stock for claimed orders, issues restock warnings |
| 🏃 **Picking Agent** | Floor & picker operations | Dispatches idle pickers to zones, tracks picker paths, reports aisle congestion factors |
| 📤 **Packing & Dispatch** | Staging & fulfillment | Monitors packing bench capacity, turns picked totes into completed parcels, manages dispatch readiness |
| 🚢 **Dock Agent** | Outbound loading | Manages dock door staging and courier handover workflows |

### Standardized MCP Tool Layer

All state access is mediated by MCP tools registered with `WarehouseMCPToolRegistry`:

| MCP Tool | Description | Parameters |
|---|---|---|
| `get_inventory_for_sku` | Fetch current stock count and shelf locations for a SKU | `sku_id: int` |
| `get_all_workers` | Retrieve status, assigned tasks, and current coordinates of all workers | _None_ |
| `get_available_workers` | Fetch idle workers qualified for pick/pack dispatch | _None_ |
| `get_zone_congestion` | Calculate active picker density across all warehouse zones (A–D) | _None_ |
| `get_packing_status` | Inspect utilization, queue depth, and status of packing stations | _None_ |
| `get_dock_status` | Inspect loading bays, doors, and courier assignment status | _None_ |
| `search_sku` | Search the product catalog by SKU name or category | `query: str` |

Every tool can also be called directly over HTTP with `POST /mcp/invoke`, and listed with `GET /mcp/tools`.

---

## Key Features

- **🔄 Dynamic multi-factor queue engine:** Orders are re-scored and re-sorted continuously based on SLA risk, worker locations, inventory presence, and congestion.
- **🤖 Decoupled A2A negotiation:** Specialist agents hand off tasks asynchronously over Redis Pub/Sub, with no tight coupling between them.
- **🗺️ Interactive SVG warehouse map:** A floorplan with shelf heatmaps (A-1 through D-6), live picker locations, packing stations, and loading docks.
- **📊 Real-time Mission Control dashboard:** 9 live KPI counters with sparklines, a zone busyness index, and throughput-vs-FIFO comparison charts.
- **💬 Live agent activity feed:** A real-time stream of inter-agent messages, decision traces, and order progress.
- **🧠 Optional Gemini commentary and re-ranking:** Read-only decision narration and opt-in batch queue re-ranking via Google's Gemini API, with an automatic fallback to rule-based scoring.
- **⚡ Dual-engine database layer:** Built for serverless Neon PostgreSQL, using pooled connections for queries and unpooled connections for DDL.
- **🔌 Native WebSocket streaming:** State updates over `/ws/live`, with cold-start detection and keep-alive heartbeats.
- **🎮 Simulation controls:** Seed the database, start and stop order generation, and switch speed (1×, 2×, 4×) on the fly.
- **🌗 Polished UI:** Dark/light theme toggle, glassmorphic cards, toast notifications, and a responsive layout.

---

## Optional LLM-Assisted Features

The platform is **fully functional without any LLM** (`LLM_PROVIDER=none`). Google's Gemini API can optionally be enabled for two independent capabilities, both designed to fail safe.

### 1. Decision Commentary (Read-Only)

- Generates a short natural-language explanation of why the dynamic engine ranked the top order #1 on the current tick.
- **Strictly read-only:** it runs after the queue has already been ranked and never changes queue order or decision outcomes.

### 2. Batch Queue Re-Ranking (`llm_batch`)

- Sends the pending order queue to Gemini in a **single batch call per tick** (never per order).
- Returns a re-ordering tagged `ranked_by: "llm"`, with a justification for each order.

### Safety Guarantees

- **Bounded latency and cost:** Exactly one API call per scoring tick.
- **Hard timeout:** Defaults to 1.0 s (`LLM_RERANK_TIMEOUT_SECONDS`). If the LLM doesn't respond in time, the tick falls back to rule-based scoring.
- **Order cap:** If the queue exceeds `LLM_RERANK_MAX_ORDERS` (default 50), the system uses rule-based scoring to avoid token exhaustion.
- **Strict ID validation:** The response must contain exactly the same set of order IDs. Any dropped, extra, or duplicated ID causes the response to be rejected, and scoring falls back to the rule-based result.
- **No state changes:** The LLM can only reorder existing IDs. It cannot create orders or modify warehouse state.

---

## Tech Stack

| Domain | Technology | Purpose |
|---|---|---|
| **Backend framework** | [FastAPI](https://fastapi.tiangolo.com/) 0.115+ (Python 3.11+) | Async REST API & WebSocket server |
| **Agent messaging** | Redis 7 / [Upstash Redis](https://upstash.com/) | Agent-to-Agent (A2A) pub/sub message bus |
| **State & database** | [Neon](https://neon.tech/) Serverless PostgreSQL 16 | Relational store via SQLAlchemy 2.0 + asyncpg |
| **State registry** | MCP-style tool registry | Standardized agent state-access layer |
| **LLM engine (optional)** | [Google Gemini 2.5](https://aistudio.google.com/) (`google-genai` SDK) | Batch re-ranking & decision commentary |
| **Frontend framework** | [Next.js](https://nextjs.org/) 16.3 (Turbopack, App Router) | Mission Control web dashboard |
| **Styling & icons** | CSS Modules + [Lucide React](https://lucide.dev/) | Glassmorphic UI & iconography |
| **Visualization** | [Recharts](https://recharts.org/) + SVG canvas | Real-time trend charts & floorplan map |
| **Cloud hosting** | [Vercel](https://vercel.com/) (frontend) + [Render](https://render.com/) (backend) | Free-tier deployment |
| **Containerization** | Docker & Docker Compose | Local development and containerized deployment |

---

## Project Structure

```
a2a-digital-twin/
├── backend/
│   ├── core/                          # Framework layer (domain-agnostic)
│   │   ├── a2a/                       #   A2A message bus & Redis connection
│   │   ├── agents/                    #   BaseAgent abstraction
│   │   ├── api/                       #   Domain-agnostic routes (/health)
│   │   ├── mcp/                       #   Base MCP registry interfaces
│   │   ├── models/                    #   Core models (AgentMessage, DecisionRecord)
│   │   ├── queue_engine/              #   Base priority queue abstractions
│   │   ├── simulation/                #   Base simulation runner
│   │   ├── config.py                  #   Pydantic Settings with multi-env loader
│   │   ├── database.py                #   Async SQLAlchemy dual engine (pooled + unpooled)
│   │   └── main.py                    #   FastAPI lifespan application entrypoint
│   │
│   ├── domains/warehouse/             # Warehouse business domain
│   │   ├── agents/                    #   Order, Inventory, Picking, Packing, Dock agents
│   │   ├── api/                       #   REST routes (/api/*) & WebSocket (/ws/live)
│   │   ├── mcp/                       #   7 warehouse MCP tools & HTTP adapter
│   │   ├── models/                    #   Order, SKU, Zone, Shelf, Worker, Station models
│   │   ├── queue_engine/              #   5-factor scorer, FIFO baseline, Gemini re-ranker
│   │   ├── services/                  #   WarehouseService & Gemini decision commentary
│   │   └── simulation/                #   Poisson order generator & database seeder
│   │
│   ├── tests/                         # Automated test suite (14 tests)
│   │   ├── test_database_config.py    #   Database protocol normalization & SSL tests
│   │   ├── test_decision_commentary.py #  LLM commentary safety & fallback tests
│   │   └── test_llm_reranker.py       #   LLM batch re-ranker & timeout safety tests
│   │
│   ├── Dockerfile                     # Multi-stage production backend container
│   ├── requirements.txt               # Backend Python dependencies
│   └── .env.example                   # Backend-specific environment template
│
├── frontend/
│   ├── src/
│   │   ├── app/                       # Next.js App Router (layout, page, globals)
│   │   ├── core/                      # Shared frontend infrastructure
│   │   │   ├── api/                   #   REST client with cold-start detection
│   │   │   ├── hooks/                 #   useWebSocket hook with keep-alive heartbeat
│   │   │   └── types/                 #   Core TypeScript definitions
│   │   ├── domains/warehouse/         # Warehouse UI components & views
│   │   │   ├── components/            #   WarehouseMap, QueueCard, KpiCard, ChatFeed
│   │   │   ├── views/                 #   DashboardView (Mission Control)
│   │   │   └── live-twin.ts           #   Computed state & metric aggregation
│   │   └── lib/                       #   Firebase initialization (optional)
│   │
│   ├── package.json                   # Frontend dependencies (Next 16, React 19)
│   ├── tsconfig.json                  # TypeScript compiler settings
│   ├── vercel.json                    # Vercel deployment blueprint
│   └── next.config.ts                 # Next.js configuration
│
├── assets/                            # Project posters, screenshots, architecture diagrams
│   └── A2A_Digital_Twin_Poster.png
├── docker-compose.yml                 # Local PostgreSQL 16 + Redis 7 infrastructure
├── Dockerfile                         # Root multi-stage container build
├── render.yaml                        # Render Web Service infrastructure-as-code
├── neon.ts                            # Neon Postgres branch lifecycle configuration
├── package.json                       # Monorepo root scripts & Neon CLI dependencies
├── .env.example                       # Root environment variable template
├── CONTRIBUTORS.md                    # Team member contributions
├── LICENSE                            # MIT License
└── README.md                          # Documentation
```

---

## Setup & Local Development

### Prerequisites

- **Python 3.11+** (3.12 recommended)
- **Node.js 20.9+** and npm (required by Next.js 16)
- **Docker Desktop**, or local PostgreSQL 16 and Redis 7 instances
- _(Optional)_ A **Google Gemini API key** for the LLM features ([Google AI Studio](https://aistudio.google.com/apikey))
- _(Optional)_ **Neon Postgres** and **Upstash Redis** accounts, if you want to develop against cloud services

### Step 1: Clone the Repository

```bash
git clone https://github.com/Maharshi-Paul/a2a-digital-twin.git
cd a2a-digital-twin
```

### Step 2: Configure Environment Variables

The backend looks for `.env` at the project root or inside `backend/`:

```bash
cp .env.example .env
```

#### Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `DOMAIN` | `warehouse` | Active domain logic |
| `DATABASE_URL` | `postgresql+asyncpg://wdt_user:wdt_pass@localhost:5432/warehouse_twin` | Primary database connection (pooled for PgBouncer / Neon) |
| `DATABASE_URL_UNPOOLED` | _Optional_ | Direct, unpooled connection string for Neon schema creation (DDL) |
| `DB_STATEMENT_CACHE_SIZE` | `0` | Keep at `0` for PgBouncer compatibility |
| `DB_POOL_SIZE` | `5` | SQLAlchemy async connection pool size |
| `DB_MAX_OVERFLOW` | `5` | Maximum pool overflow connections |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL (`rediss://` supported for TLS) |
| `REDIS_MAX_CONNECTIONS` | `10` | Redis connection pool cap |
| `API_HOST` | `0.0.0.0` | Backend bind host |
| `API_PORT` | `8000` | Backend bind port |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed frontend origins (comma-separated) |
| `FRONTEND_URL` | _Optional_ | Additional production frontend URL |
| `QUEUE_TICK_SECONDS` | `10.0` | Interval between priority-queue scoring cycles |
| `QUEUE_ENGINE_MODE` | `rule_based` | Scoring mode: `rule_based` or `llm_batch` |
| `QUEUE_ENGINE_IDLE_WHEN_EMPTY` | `true` | Skip scoring when no orders are pending |
| `W_SLA_RISK` | `0.35` | Weight $w_1$ for SLA risk |
| `W_WAIT_TIME` | `0.15` | Weight $w_2$ for wait time |
| `W_INVENTORY_READINESS` | `0.25` | Weight $w_3$ for inventory readiness |
| `W_AISLE_CONGESTION` | `0.10` | Weight $w_4$ for aisle congestion |
| `W_PACKING_CAPACITY` | `0.15` | Weight $w_5$ for packing capacity |
| `SIMULATION_SEED` | `42` | Random seed for deterministic replay |
| `SIMULATION_LAMBDA` | `3.0` | Poisson order arrival rate (orders per minute) |
| `LLM_PROVIDER` | `none` | LLM switch: `none` or `gemini` |
| `GEMINI_API_KEY` | _None_ | Google AI Studio API key |
| `LLM_MODEL` | `gemini-2.5-flash-lite` | Gemini model name |
| `LLM_RERANK_TIMEOUT_SECONDS` | `1.0` | Maximum wait for batch LLM re-ranking |
| `LLM_RERANK_MAX_ORDERS` | `50` | Maximum orders per batch before falling back |
| `ADMIN_TOKEN` | _None_ | Optional shared token that protects simulation endpoints |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend base URL used by the frontend |
| `NEXT_PUBLIC_WS_URL` | `ws://localhost:8000/ws/live` | WebSocket endpoint used by the frontend |

### Step 3: Start Infrastructure (Docker)

To run PostgreSQL and Redis locally:

```bash
docker compose up -d
docker ps    # expect wdt_postgres and wdt_redis both "Up"
```

> [!TIP]
> Using cloud databases (Neon PostgreSQL, Upstash Redis)? Skip Docker Compose and point `DATABASE_URL` and `REDIS_URL` at your cloud endpoints.

### Step 4: Install Dependencies

**Backend** (a virtual environment is recommended):

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```

**Frontend:**

```bash
cd frontend
npm install
cd ..
```

### Step 5: Start the Backend

```bash
cd backend
python -m uvicorn core.main:app --reload --host 0.0.0.0 --port 8000
```

On startup the backend automatically:

1. Connects to PostgreSQL and verifies the schema using the unpooled engine.
2. Seeds default zones (A, B, C, D), shelves (A-1 to D-6), SKUs, workers, and packing stations.
3. Opens the Redis A2A message bus connection.
4. Initializes all 5 autonomous agents.
5. Starts the periodic queue scoring engine and order generator.

Useful endpoints:

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health check:** [http://localhost:8000/health](http://localhost:8000/health)
- **Live WebSocket:** `ws://localhost:8000/ws/live`

### Step 6: Start the Frontend

In a separate terminal:

```bash
cd frontend
npm run dev
```

Open **[http://localhost:3000](http://localhost:3000)** to see the Mission Control dashboard.

---

## Testing & Quality Assurance

The automated suite covers database URL normalization, SSL auto-negotiation, the PgBouncer statement-cache setting, Gemini decision commentary, and the LLM batch re-ranker's safety fallbacks.

From the repository root:

```bash
python -m pytest backend/tests -o pythonpath=backend -v
```

Or from inside `backend/`:

```bash
cd backend
pytest -v
```

### Test Coverage

- **`test_database_config.py`**
  - Normalizes `postgres://` and `postgresql://` URLs to `postgresql+asyncpg://`.
  - Strips `sslmode=require` query parameters for asyncpg and replaces them with a valid `ssl.SSLContext`.
  - Confirms `statement_cache_size=0` is set for PgBouncer poolers.
- **`test_decision_commentary.py`**
  - Verifies that commentary never alters queue scores.
  - Tests timeout resilience and fallback behavior when the Gemini API is unreachable.
- **`test_llm_reranker.py`**
  - Tests single-batch re-ranking against mock Gemini responses.
  - Verifies rejection of responses with missing, extra, or duplicate order IDs.
  - Verifies fallback to rule-based scoring on network timeouts and queue-size overflow.

---

## REST API & WebSocket Reference

### Health & System

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Basic liveness probe (`{"status": "healthy"}`) |
| `GET` | `/health?detailed=true` | Deep probe that runs a live database query |
| `GET` | `/docs` | Interactive Swagger UI |

### Simulation Management

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/simulation/status` | Current status and total generated order count |
| `POST` | `/api/simulation/start` | Start the Poisson order generator |
| `POST` | `/api/simulation/stop` | Pause order generation |
| `POST` | `/api/simulation/seed` | Reset and re-seed the warehouse layout, SKUs, and stations |

> [!NOTE]
> If `ADMIN_TOKEN` is set, mutation endpoints require the header `X-Admin-Token: <token>`.

### Warehouse State & Priority Queue

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/orders` | List orders, with optional `status`, `limit`, and `offset` |
| `GET` | `/api/orders/counts` | Order counts by status |
| `GET` | `/api/queue` | Current priority ranking with factor scores and breakdown |
| `GET` | `/api/queue/fifo` | Baseline FIFO order sequence |
| `GET` | `/api/queue/comparison` | Side-by-side comparison of AI priority and FIFO ranks |
| `GET` | `/api/warehouse/status` | Snapshot of zones, shelves, workers, and stations |
| `GET` | `/api/warehouse/kpis` | Live KPIs (waiting time, utilization, SLA breach rate) |
| `GET` | `/api/agent-logs` | Recent inter-agent negotiation messages from the A2A bus |
| `GET` | `/api/decisions/traces` | Full negotiation traces and resolution outcomes |
| `GET` | `/api/decisions/records` | Step-by-step decision records and agent reasoning |

### Model Context Protocol (MCP) Interface

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/mcp/tools` | List all registered MCP tools and their parameter schemas |
| `POST` | `/mcp/invoke` | Invoke a tool: `{"tool_name": "...", "parameters": {...}}` |

### WebSocket Streaming

- **Endpoint:** `ws://localhost:8000/ws/live` (`wss://...` in production)
- **Payload:** a JSON snapshot every tick, containing:
  - `warehouse`: facility state, zone congestion, worker locations, and packing loads.
  - `queue`: current queue scores, top-order breakdown, and comparison metrics.
  - `kpis`: 9 live operational KPIs with historical sparklines.
  - `agent_logs`: latest agent conversations and decision rationales.
- **Heartbeat:** the server pings every 25 seconds to prevent proxy timeouts.

---

## Production Cloud Deployment Guide

The platform is designed to run on free tiers: **Vercel** for the frontend, **Render** for the backend, **Neon** for managed PostgreSQL, and **Upstash** or **Render Key Value** for Redis.

```mermaid
graph LR
    V["Vercel<br/>Next.js 16 app"] <-->|WebSocket / REST| R["Render<br/>FastAPI container"]
    R --> N[("Neon<br/>PostgreSQL")]
    R --> U[("Upstash<br/>Redis")]
```

### 1. Database: Neon PostgreSQL

1. Create a serverless PostgreSQL instance at [neon.tech](https://neon.tech).
2. From the Neon dashboard, copy both connection strings:
   - `DATABASE_URL`: the pooled (PgBouncer) string, whose host ends in `-pooler`.
   - `DATABASE_URL_UNPOOLED`: the direct string, used for DDL schema creation.
3. The backend strips incompatible parameters (such as `sslmode`), configures an SSL context, and sets `statement_cache_size=0` automatically.

### 2. Redis: Upstash or Render Key Value

1. Create a Redis database at [upstash.com](https://upstash.com), or use **Render Key Value**.
2. For Upstash, copy the TLS URL, which starts with `rediss://`.
3. The backend negotiates TLS automatically (`ssl_cert_reqs="none"`), so certificate-validation errors don't occur.

### 3. Backend: Render Web Service

1. Connect your repository on [render.com](https://render.com).
2. Choose the **Docker** runtime, using either `backend/Dockerfile` or the root `render.yaml` blueprint.
3. Set these environment variables in the Render dashboard:

   ```env
   PORT=8000
   DATABASE_URL=postgresql+asyncpg://<neon-pooled-url>
   DATABASE_URL_UNPOOLED=postgresql+asyncpg://<neon-unpooled-url>
   REDIS_URL=rediss://<upstash-redis-url>
   CORS_ORIGINS=https://your-frontend.vercel.app
   FRONTEND_URL=https://your-frontend.vercel.app
   QUEUE_TICK_SECONDS=10.0
   QUEUE_ENGINE_MODE=rule_based
   LLM_PROVIDER=none
   ```

4. Set Render's health check path to `/health`.

### 4. Frontend: Vercel

1. Import your GitHub repository on [vercel.com](https://vercel.com).
2. Set the **Root Directory** to `frontend`.
3. Add these environment variables:

   ```env
   NEXT_PUBLIC_API_URL=https://your-backend.onrender.com
   NEXT_PUBLIC_WS_URL=wss://your-backend.onrender.com/ws/live
   ```

4. Deploy. The frontend detects Render free-tier cold starts and shows a waking-up indicator until the backend is ready.

---

## Usage Guide

1. **Launch Mission Control:** open [http://localhost:3000](http://localhost:3000).
2. **Seed the database:** click **Seed DB** in the header to populate (or reset) zones, shelves, SKUs, workers, and stations.
3. **Start the simulation:** click **Start Sim** to activate the Poisson order generator.
4. **Monitor operations:**
   - **KPI strip:** total orders, active pickers, SLA breach rate, and throughput.
   - **Warehouse floorplan:** pickers moving between zones A to D while shelf inventory depletes.
   - **Priority queue:** the 5-factor score breakdown behind each order's rank.
   - **Throughput vs. FIFO:** how dynamic priority reduces SLA breaches compared with the FIFO baseline.
   - **Agent activity feed:** live negotiation between the Order, Inventory, Picking, and Packing agents.
5. **Change the simulation speed:** use the `1x`, `2x`, and `4x` buttons.
6. **Switch theme:** toggle dark or light mode from the navigation bar.

---

## Validation Targets

Policies are compared on identical synthetic order streams (`SIMULATION_SEED=42`). These are the outcomes the engine is designed to achieve relative to FIFO:

| Metric | Description | Expected Outcome vs. FIFO |
|---|---|---|
| **Average waiting time** | Time from order creation to pick assignment | Significant reduction for multi-item and high-urgency orders |
| **Throughput** | Orders completed and dispatched per hour | Higher sustained throughput by avoiding packing congestion |
| **Picker utilization** | Ratio of active picking time to idle transit time | More balanced distribution across zones, with less picker crowding |
| **SLA breach rate** | Share of orders delivered past their SLA deadline | Measurable drop from prioritizing urgent orders |
| **Packing bottleneck** | Queue depth of totes waiting for packing benches | Smoother packing queue via feedback-driven picking throttling |
| **LLM fallback rate** | How often `llm_batch` falls back to rule-based scoring | Tracked to confirm the system stays available when the API is slow or rate-limited |

---

## Known Limitations & Roadmap

### Known Limitations

- **Synthetic data only:** orders come from a Poisson generator, and there is no live warehouse management system (WMS) integration yet.
- **Single facility:** the twin models one dark store.
- **Cold starts:** on Render's free tier, the first load after idle can be slow while the backend wakes up.
- **Bounded LLM re-ranking:** a 1.0 s timeout and a 50-order cap apply, and beyond them scoring falls back to the rule-based engine.
- **Minimal access control:** protection is limited to the optional shared `ADMIN_TOKEN`, with no user accounts or roles.

### Roadmap

- [x] **Dynamic 5-factor priority scorer** with configurable real-time weights
- [x] **Autonomous A2A multi-agent architecture** coordinated over Redis Pub/Sub
- [x] **Standardized MCP tool layer** with 7 warehouse tools and HTTP invocation
- [x] **No Firebase dependency** (native WebSockets and REST)
- [x] **Optional Gemini 2.5 integration** for decision commentary and batch re-ranking, with automatic fallback
- [x] **Cloud deployment** guides and blueprints for Vercel, Render, Neon, and Upstash
- [ ] **Multi-facility orchestration** across multiple dark stores and regional hubs
- [ ] **Real-world WMS connectors** for live feeds from Manhattan Associates, Blue Yonder, and SAP EWM
- [ ] **Autonomous AGV navigation** via ROS2 for automated guided vehicle dispatching
- [ ] **Role-based access control** with user authentication for enterprise warehouse staff

---

## Contributors

See [CONTRIBUTORS.md](./CONTRIBUTORS.md) for team members and roles.

---

## License

This project is licensed under the MIT License. See the [LICENSE](./LICENSE) file for details.
