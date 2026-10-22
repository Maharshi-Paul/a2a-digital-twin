<p align="center">
  <img src="assets/A2A_Digital_Twin_Poster.png" alt="A2A Digital Twin — Warehouse" width="100%">
</p>

<h1 align="center">A2A Digital Twin — Warehouse</h1>

<p align="center">
  <b>A simulated warehouse digital twin that replaces static FIFO queues with a dynamic, negotiated priority engine — coordinated by autonomous agents over A2A, with state accessed through an MCP-style tool layer.</b>
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

## Problem

Quick-commerce dark stores and micro-fulfillment centers operate under strict SLA windows (e.g., 10–30 minute deliveries). However, conventional facilities rely on fixed **FIFO (First-In, First-Out) order queues**. Under FIFO:
- High-value orders on the verge of breaching their SLA are stranded behind low-priority single-item orders with hours of slack.
- Pickers congest the same warehouse aisles simultaneously, inducing physical floor bottlenecks.
- Work is released to picking without regard for packing station availability, causing staging area gridlock.

The result is **avoidable SLA penalties, uneven worker utilization, and fulfillment delays** that an intelligent, state-aware dispatch system can prevent.

---

## Solution

**A2A Digital Twin** is an agentic, queue-aware warehouse simulation and orchestration platform. It replaces static FIFO dispatching with a **dynamic priority engine** governed by autonomous specialist agents communicating over an **Agent-to-Agent (A2A)** message bus and interacting with real warehouse state via a standardized **MCP (Model Context Protocol)** tool layer.

```mermaid
graph LR
    A[📦 Synthetic Order Stream] --> B[Order Coordinator]
    B --> C[Dynamic Priority Engine]
    C --> D[Inventory Agent]
    C --> E[Picking Agent]
    C --> F[Packing & Dispatch Agent]
    D <-->|A2A Bus - Redis Pub/Sub| E
    E <-->|A2A Bus - Redis Pub/Sub| F
    D ---|MCP Tools| G[(Neon / PostgreSQL 16)]
    E ---|MCP Tools| G
    F ---|MCP Tools| G
    B -->|Native WebSocket ws://| H[📊 Live Next.js 16 Dashboard]
    B -.->|Optional Sync| I[🔥 Firebase Firestore]
```

### End-to-End Orchestration Flow:
1. **Order Ingestion:** Poisson-distributed synthetic orders enter through the API and are registered by the **Order Coordinator Agent**.
2. **Dynamic Priority Scoring:** Orders are continually scored and re-ranked using a 5-factor scoring model that accounts for SLA urgency, wait time, inventory readiness, aisle congestion, and packing capacity.
3. **Multi-Agent Negotiation:** Specialist agents (**Inventory**, **Picking**, **Packing & Dispatch**, and **Dock**) negotiate assignment over the **A2A Redis message bus**.
4. **Standardized State Access:** State reads and status mutations execute through safe, decoupled **MCP tools** backed by an async SQLAlchemy database layer.
5. **Real-Time Telemetry:** State broadcasts over a native **WebSocket channel** (`/ws/live`) with a 25-second heartbeat loop and cold-start health probes, updating a high-fidelity **Next.js 16 Mission Control Dashboard**.
6. **Policy Benchmarking:** The engine supports deterministic replay of synthetic workloads across **FIFO baseline**, **Rule-Based Dynamic Priority**, and **LLM-Assisted Batch Re-Ranking** for empirical comparison.

> **Data Authenticity & Zero Lock-In Guarantee:**
> - **100% Real Backend State:** Priority scores, SLA countdowns, aisle congestion metrics, and inter-agent dialogues are calculated by the FastAPI backend and broadcast over native WebSockets and REST APIs.
> - **Facility Canvas Visualization:** The 2D SVG warehouse floorplan maps real PostgreSQL shelf inventory and worker coordinates into an interactive visual canvas.
> - **Zero Firebase Lock-In:** The entire application runs natively over WebSockets and REST endpoints. Firebase Firestore sync is completely optional and disabled by default.

---

## Priority Scoring Formula

The core dynamic priority engine evaluates pending orders every tick using a weighted multi-factor scoring function:

$$\text{Priority Score} = w_1 \cdot \text{SLA\_Risk} + w_2 \cdot \text{Wait\_Time} + w_3 \cdot \text{Inv\_Readiness} + w_4 \cdot \text{Congestion\_Factor} + w_5 \cdot \text{Packing\_Factor}$$

| Factor | Weight | Formula / Definition | Objective |
|---|---|---|---|
| **SLA Risk** | $w_1 = 0.35$ | $\max\left(0, 1 - \frac{\text{minutes\_remaining}}{\text{max\_sla\_window}}\right)$ | Expedite orders approaching SLA breach |
| **Wait Time** | $w_2 = 0.15$ | $\min\left(1, \frac{\text{elapsed\_wait\_minutes}}{\text{max\_wait\_window}}\right)$ | Prevent queue starvation for older orders |
| **Inventory Readiness** | $w_3 = 0.25$ | $\frac{\sum \text{available items in stock}}{\text{total order items requested}}$ | Prioritize orders ready for immediate picking |
| **Aisle Congestion** | $w_4 = 0.10$ | $1.0 - \text{average congestion of target zones}$ | Route pickers away from crowded aisles |
| **Packing Capacity** | $w_5 = 0.15$ | $1.0 - \text{overall packing station utilization}$ | Throttles picking when packing tables are full |

All weights sum to $1.00$ and can be customized via environment variables (`W_SLA_RISK`, `W_WAIT_TIME`, `W_INVENTORY_READINESS`, `W_AISLE_CONGESTION`, `W_PACKING_CAPACITY`).

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
| 🎯 **Order Coordinator** | Orchestrator & Dispatcher | Ingests incoming orders, triggers periodic queue scoring, negotiates task assignments, streams live traces |
| 📦 **Inventory Agent** | Stock & Replenishment | Audits SKU availability across shelves (A-1 to D-6), reserves stock for claimed orders, issues restock warnings |
| 🏃 **Picking Agent** | Floor & Picker Operations | Dispatches idle pickers to zones, tracks picker paths, reports aisle congestion factors |
| 📤 **Packing & Dispatch** | Stage & Fulfillment | Monitors packing bench capacity, transitions picked totes into completed parcels, manages dispatch readiness |
| 🚢 **Dock Agent** | Outbound Loading | Manages dock door staging and courier handover workflows |

### Standardized MCP Tool Layer

State access is strictly mediated by MCP tools registered with `WarehouseMCPToolRegistry`:

| MCP Tool Name | Description | Parameters |
|---|---|---|
| `get_inventory_for_sku` | Fetch current stock count and shelf locations for a SKU | `sku_id: int` |
| `get_all_workers` | Retrieve status, assigned tasks, and current coordinates of all workers | _None_ |
| `get_available_workers` | Fetch idle workers qualified for pick/pack dispatch | _None_ |
| `get_zone_congestion` | Calculate active picker density across all warehouse zones (A–D) | _None_ |
| `get_packing_status` | Inspect utilization, queue depth, and status of packing stations | _None_ |
| `get_dock_status` | Inspect loading bays, doors, and courier assignment status | _None_ |
| `search_sku` | Search product catalog by SKU name or category | `query: str` |

All tools can also be invoked directly over HTTP via `POST /mcp/invoke` or inspected via `GET /mcp/tools`.

---

## Key Features

- **🔄 Dynamic Multi-Factor Queue Engine:** Orders re-scored and sorted dynamically based on SLA risks, worker locations, inventory presence, and congestion.
- **🤖 Decoupled A2A Negotiation:** Specialist agents coordinate task handover asynchronously via Redis Pub/Sub without tight coupling.
- **🗺️ Interactive SVG Warehouse Map:** Visual floorplan displaying shelf heatmaps (A-1 through D-6), real-time picker locations, packing stations, and loading docks.
- **📊 Real-Time Mission Control Dashboard:** 9 live KPI counters with sparkline trends, zone busyness index, and throughput vs. FIFO comparison charts.
- **💬 Live Agent Activity Feed:** Real-time stream of inter-agent messages, decision traces, and order progress.
- **🧠 Optional Gemini-Powered AI Commentary & Re-Ranking:** Read-only decision narration and opt-in batch queue re-ranking via Google's Gemini API with 100% fail-safe fallback.
- **⚡ Dual Engine Database Architecture:** Optimized for serverless Neon PostgreSQL with pooled connections for queries and unpooled connections for DDL schema creation.
- **🔌 Native WebSocket & Zero Lock-In:** Real-time state updates streamed over native WebSocket (`/ws/live`) with cold-start detection and keep-alive heartbeats.
- **🎮 Granular Simulation Controls:** Seed database, start/stop order generation, and adjust simulation speeds (1×, 2×, 4×) on the fly.
- **🌗 Modern UI Aesthetics:** Sleek dark/light theme toggle, glassmorphic cards, toast notification alerts, and full responsiveness.

---

## Optional LLM-Assisted Features

The platform is designed to be **100% functional without any LLM configured** (`LLM_PROVIDER=none`). When desired, Google's Gemini API can be enabled for two independent, fail-safe capabilities:

### 1. Decision Commentary (Read-Only)
- Generates a concise, natural-language explanation of why the dynamic engine ranked the top order #1 in the current tick.
- **Strictly Read-Only:** Operates after the queue has already been ranked; never modifies queue order or decision outcomes.

### 2. Batch Queue Re-Ranking (`llm_batch`)
- Sends the pending order queue to Gemini in a **single API batch call per tick** (never per order).
- Returns an intelligent re-ordering tagged `ranked_by: "llm"` accompanied by per-order justifications.

### Bulletproof Safety Guarantees:
- **Bounded Latency & Cost:** Exactly one API call per scoring tick.
- **Hard Timeout:** Defaults to 1.0s (`LLM_RERANK_TIMEOUT_SECONDS`). If the LLM does not respond in time, the tick cleanly defaults to rule-based scoring.
- **Order Cap Safety:** If the queue exceeds `LLM_RERANK_MAX_ORDERS` (default 50), the system automatically defaults to rule-based scoring to prevent token exhaustion.
- **Strict ID Set Validation:** The returned response must contain an exact 1:1 match of order IDs. Any dropped, extra, or duplicated IDs result in immediate rejection and safe fallback.
- **Zero Hallucination Vulnerability:** The LLM only orders existing IDs; it cannot create fake orders or modify warehouse state.

---

## Tech Stack

| Domain | Technology | Purpose |
|---|---|---|
| **Backend Framework** | [FastAPI](https://fastapi.tiangolo.com/) 0.115+ (Python 3.11+) | Async REST API & WebSocket server |
| **Agent Messaging** | Redis 7 / [Upstash Redis](https://upstash.com/) | Agent-to-Agent (A2A) pub/sub message bus |
| **State & Database** | [Neon](https://neon.tech/) Serverless PostgreSQL 16 | Relational store via SQLAlchemy 2.0 + asyncpg |
| **State Registry** | MCP-Style Tool Registry | Standardized agent state access layer |
| **LLM Engine (Optional)** | [Google Gemini 2.5](https://aistudio.google.com/) (`google-genai` SDK) | Batch re-ranking & decision commentary |
| **Frontend Framework** | [Next.js](https://nextjs.org/) 16.3 (Turbopack, App Router) | Mission control web dashboard |
| **Styling & Icons** | CSS Modules + [Lucide React](https://lucide.dev/) | Glassmorphic UI & iconography |
| **Visualizations** | [Recharts](https://recharts.org/) + SVG Canvas | Real-time trend analytics & floorplan map |
| **Cloud Hosting** | [Vercel](https://vercel.com/) (Frontend) + [Render](https://render.com/) (Backend) | Zero-cost serverless deployment |
| **Containerization** | Docker & Docker Compose | Local development and containerized deployment |

---

## Project Structure

```
a2a-digital-twin/
├── backend/
│   ├── core/                          # Framework Layer (Domain-agnostic)
│   │   ├── a2a/                       #   A2A Message Bus & Redis connection
│   │   ├── agents/                    #   BaseAgent abstraction
│   │   ├── api/                       #   Domain-agnostic routes (/health)
│   │   ├── mcp/                       #   Base MCP registry interfaces
│   │   ├── models/                    #   Core models (AgentMessage, DecisionRecord)
│   │   ├── queue_engine/              #   Base priority queue abstractions
│   │   ├── simulation/                #   Base simulation runner
│   │   ├── config.py                  #   Pydantic Settings with multi-env loader
│   │   ├── database.py               #   Async SQLAlchemy dual-engine (pooled + unpooled)
│   │   └── main.py                    #   FastAPI lifespan application entrypoint
│   │
│   ├── domains/warehouse/             # Warehouse Business Domain
│   │   ├── agents/                    #   Order, Inventory, Picking, Packing, Dock agents
│   │   ├── api/                       #   REST routes (/api/*) & WebSocket (/ws/live)
│   │   ├── mcp/                       #   7 Warehouse MCP Tools & HTTP adapter
│   │   ├── models/                    #   Order, SKU, Zone, Shelf, Worker, Station models
│   │   ├── queue_engine/              #   5-factor scorer, FIFO baseline, Gemini re-ranker
│   │   ├── services/                  #   WarehouseService & Gemini decision commentary
│   │   └── simulation/                #   Poisson order generator & database seeder
│   │
│   ├── tests/                         # Automated Test Suite (14 tests)
│   │   ├── test_database_config.py    #   Database protocol normalization & SSL tests
│   │   ├── test_decision_commentary.py#   LLM commentary safety & fallback tests
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
├── render.yaml                        # Render Web Service Infrastructure-as-Code
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

- **Python 3.11+** (Python 3.12 recommended)
- **Node.js 18+** & npm
- **Docker Desktop** (or local PostgreSQL 16 & Redis 7 instances)
- _(Optional)_ **Google Gemini API Key** for LLM features ([Google AI Studio](https://aistudio.google.com/apikey))
- _(Optional)_ **Neon Postgres** and **Upstash Redis** accounts for cloud-native local development

---

### Step 1: Clone the Repository

```bash
git clone https://github.com/Maharshi-Paul/a2a-digital-twin.git
cd a2a-digital-twin
```

---

### Step 2: Configure Environment Variables

Create your `.env` configuration. The backend automatically looks for `.env` at the project root or inside `backend/`:

```bash
cp .env.example .env
```

#### Environment Variables Reference

| Variable | Default Value | Description |
|---|---|---|
| `DOMAIN` | `warehouse` | Active domain logic |
| `DATABASE_URL` | `postgresql+asyncpg://wdt_user:wdt_pass@localhost:5432/warehouse_twin` | Primary database connection (pooled for PgBouncer / Neon) |
| `DATABASE_URL_UNPOOLED` | _Optional_ | Direct unpooled connection string for Neon schema creation/DDL |
| `DB_STATEMENT_CACHE_SIZE` | `0` | Set to `0` for PgBouncer connection pooler compatibility |
| `DB_POOL_SIZE` | `5` | SQLAlchemy async connection pool size |
| `DB_MAX_OVERFLOW` | `5` | Max pool overflow connections |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL (`rediss://` supported for TLS) |
| `REDIS_MAX_CONNECTIONS` | `10` | Redis connection pool cap |
| `API_HOST` | `0.0.0.0` | Backend bind host |
| `API_PORT` | `8000` | Backend bind port |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed frontend origins (comma-separated) |
| `FRONTEND_URL` | _Optional_ | Additional production frontend URL |
| `QUEUE_TICK_SECONDS` | `10.0` | Priority queue scoring cycle interval |
| `QUEUE_ENGINE_MODE` | `rule_based` | Scoring mode: `"rule_based"` or `"llm_batch"` |
| `QUEUE_ENGINE_IDLE_WHEN_EMPTY`| `true` | Skips scoring when no orders are pending |
| `SIMULATION_SEED` | `42` | Random seed for deterministic replay |
| `SIMULATION_LAMBDA` | `3.0` | Poisson order arrival rate (orders/minute) |
| `LLM_PROVIDER` | `none` | LLM switch: `"none"` or `"gemini"` |
| `GEMINI_API_KEY` | _None_ | Google AI Studio API Key |
| `LLM_MODEL` | `gemini-2.5-flash-lite` | Gemini model name |
| `LLM_RERANK_TIMEOUT_SECONDS` | `1.0` | Maximum wait time for batch LLM re-ranking |
| `LLM_RERANK_MAX_ORDERS` | `50` | Maximum orders per batch before falling back |
| `ADMIN_TOKEN` | _None_ | Optional shared token to secure simulation endpoints |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend base URL used by frontend |
| `NEXT_PUBLIC_WS_URL` | `ws://localhost:8000/ws/live` | WebSocket stream endpoint used by frontend |

---

### Step 3: Start Infrastructure (Docker)

If running PostgreSQL and Redis locally via Docker:

```bash
docker compose up -d
```

Verify containers are running:
```bash
docker ps
# Expected: wdt_postgres and wdt_redis both "Up"
```

> **Note:** If you are using cloud databases (such as Neon PostgreSQL and Upstash Redis), you can skip Docker Compose entirely and point `DATABASE_URL` and `REDIS_URL` to your cloud endpoints.

---

### Step 4: Install Dependencies

#### 1. Backend Dependencies:
```bash
pip install -r backend/requirements.txt
```

#### 2. Frontend Dependencies:
```bash
cd frontend
npm install
cd ..
```

---

### Step 5: Start the Backend Service

```bash
cd backend
python -m uvicorn core.main:app --reload --host 0.0.0.0 --port 8000
```

Upon startup, the backend automatically:
1. Connects to PostgreSQL and verifies schema tables using the unpooled engine.
2. Seeds default zones (A, B, C, D), shelves (A-1 to D-6), SKUs, workers, and packing stations.
3. Establishes the Redis A2A message bus connection.
4. Initializes all 5 autonomous agents.
5. Starts the periodic queue scoring engine and order generator.

- **API Documentation (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check Endpoint:** [http://localhost:8000/health](http://localhost:8000/health)
- **Live WebSocket Endpoint:** `ws://localhost:8000/ws/live`

---

### Step 6: Start the Frontend Application

In a separate terminal:

```bash
cd frontend
npm run dev
```

Open **[http://localhost:3000](http://localhost:3000)** in your browser to access the mission-control dashboard.

---

## Testing & Quality Assurance

The codebase includes an automated test suite verifying database normalization, SSL auto-negotiation, PgBouncer statement cache settings, Gemini decision commentary, and LLM batch re-ranker safety fallbacks.

Run the tests from the repository root:

```bash
python -m pytest backend/tests -o pythonpath=backend -v
```

Or from inside `backend/`:

```bash
cd backend
pytest -v
```

### Test Coverage Highlights:
- **`test_database_config.py`:**
  - Validates protocol normalization from `postgres://` and `postgresql://` to `postgresql+asyncpg://`.
  - Ensures `sslmode=require` query parameters are safely stripped for asyncpg and replaced with valid `ssl.SSLContext`.
  - Verifies `statement_cache_size=0` is configured for PgBouncer connection poolers.
- **`test_decision_commentary.py`:**
  - Verifies that decision commentary never alters queue scores.
  - Tests timeout resilience and fallback behavior when Gemini API is unreachable.
- **`test_llm_reranker.py`:**
  - Tests single-batch re-ranking with mock Gemini responses.
  - Verifies rejection of responses with missing, extraneous, or duplicate order IDs.
  - Verifies automatic fallback to rule-based scoring upon network timeouts or queue size overflow.

---

## REST API & WebSocket Reference

### Health & System Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Basic liveness probe (`{"status": "healthy"}`) |
| `GET` | `/health?detailed=true` | Deep probe executing an active database query |
| `GET` | `/docs` | Interactive Swagger UI API documentation |

### Simulation Management Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/simulation/status` | Current status and total generated order count |
| `POST` | `/api/simulation/start` | Start the Poisson order generator stream |
| `POST` | `/api/simulation/stop` | Pause the order generation process |
| `POST` | `/api/simulation/seed` | Reset and re-seed warehouse layout, SKUs, and stations |

> **Security Note:** If `ADMIN_TOKEN` is set in the environment, mutation endpoints require the `X-Admin-Token: <token>` header.

### Warehouse State & Priority Queue

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/orders` | List orders with optional `status`, `limit`, and `offset` |
| `GET` | `/api/orders/counts` | Breakdown of order counts by status |
| `GET` | `/api/queue` | Current priority queue ranking, factor scores, and breakdown |
| `GET` | `/api/queue/fifo` | Baseline FIFO order sequence |
| `GET` | `/api/queue/comparison` | Side-by-side comparison between AI Priority and FIFO ranks |
| `GET` | `/api/warehouse/status` | Comprehensive snapshot of zones, shelves, workers, and stations |
| `GET` | `/api/warehouse/kpis` | Real-time calculated KPIs (waiting time, utilization, SLA breach rate) |
| `GET` | `/api/agent-logs` | Recent inter-agent negotiation messages on the A2A bus |
| `GET` | `/api/decisions/traces` | Full negotiation traces and resolution outcomes |
| `GET` | `/api/decisions/records` | Step-by-step decision records and agent reasoning |

### Model Context Protocol (MCP) Interface

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/mcp/tools` | Enumerate all registered MCP tools and parameter schemas |
| `POST` | `/mcp/invoke` | Invoke an MCP tool dynamically (`{"tool_name": "...", "parameters": {...}}`) |

### Native WebSocket Streaming

- **Endpoint:** `ws://localhost:8000/ws/live` (or `wss://...` in production)
- **Protocol:** Broadcasts JSON snapshots every tick containing:
  - `warehouse`: Complete facility state, zone congestion, worker locations, and packing loads.
  - `queue`: Current dynamic queue scores, top order breakdown, and comparison metrics.
  - `kpis`: 9 live calculated operational KPIs with historical sparklines.
  - `agent_logs`: Latest agent conversations and decision rationales.
- **Heartbeat:** Includes an automatic 25-second server ping/pong heartbeat to prevent proxy timeout disconnects.

---

## Production Cloud Deployment Guide

The platform is architected for zero-cost deployment using **Vercel** for the frontend, **Render** for the backend, **Neon** for managed PostgreSQL, and **Upstash / Render Key Value** for Redis:

```
┌─────────────────┐       WebSocket / REST        ┌─────────────────────────┐
│     Vercel      │ ────────────────────────────> │         Render          │
│ Next.js 16 App  │ <──────────────────────────── │ FastAPI Container       │
└─────────────────┘                               └─────────────────────────┘
                                                        │              │
                                                        ▼              ▼
                                                ┌────────────┐   ┌────────────┐
                                                │    Neon    │   │  Upstash   │
                                                │ PostgreSQL │   │   Redis    │
                                                └────────────┘   └────────────┘
```

### 1. Database Setup: Neon PostgreSQL
1. Create a serverless PostgreSQL instance on [neon.tech](https://neon.tech).
2. Obtain both the **Pooled** and **Direct / Unpooled** connection strings from your Neon dashboard:
   - `DATABASE_URL`: Connection string pointing to the PgBouncer pooler (ends with `-pooler`).
   - `DATABASE_URL_UNPOOLED`: Direct connection string used for DDL schema creation.
3. The backend automatically strips incompatible parameters (such as `sslmode`), configures an SSL context, and sets `statement_cache_size=0`.

### 2. Redis Setup: Upstash Redis / Render Key Value
1. Create a Redis database on [upstash.com](https://upstash.com) or use **Render Key Value**.
2. For Upstash, copy the TLS connection URL starting with `rediss://`.
3. The backend automatically negotiates TLS without certificate validation errors (`ssl_cert_reqs="none"`).

### 3. Backend Deployment: Render Web Service
1. Connect your repository on [render.com](https://render.com).
2. Select **Docker** runtime (using `backend/Dockerfile` or the root `render.yaml` blueprint).
3. Set the following Environment Variables in the Render dashboard:
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
4. Render's health check probe uses `/health`.

### 4. Frontend Deployment: Vercel
1. Import your GitHub repository on [vercel.com](https://vercel.com).
2. Set the **Root Directory** to `frontend`.
3. Configure the following Environment Variables:
   ```env
   NEXT_PUBLIC_API_URL=https://your-backend.onrender.com
   NEXT_PUBLIC_WS_URL=wss://your-backend.onrender.com/ws/live
   ```
4. Deploy! The frontend automatically detects Render free-tier cold starts and displays a waking-up progress indicator until the backend is fully initialized.

---

## Usage Guide

1. **Launch Mission Control:** Open the dashboard at [http://localhost:3000](http://localhost:3000).
2. **Seed Warehouse Database:** Click the **Seed DB** button in the header to populate the database with zones, shelves, SKUs, workers, and stations.
3. **Start Simulation:** Click **Start Sim** to activate the Poisson synthetic order generator.
4. **Monitor Real-Time Operations:**
   - **KPI Strip:** Track total orders, active pickers, SLA breach rates, and throughput in real time.
   - **Warehouse Floorplan:** Watch pickers navigate between zones (A to D) and observe shelf inventory depleting.
   - **Priority Queue:** Inspect why orders are prioritized based on their 5-factor breakdown scores.
   - **Throughput vs. FIFO:** Observe how dynamic priority mitigates SLA breaches compared to the standard FIFO queue.
   - **Agent Activity Feed:** Follow real-time negotiation messages between Order, Inventory, Picking, and Packing agents.
5. **Adjust Simulation Parameters:** Accelerate the clock with speed buttons (`1x`, `2x`, `4x`).
6. **Toggle Theme:** Switch between dark and light modes with the navigation bar toggle.

---

## Validation Targets

Operational gains are measured under identical synthetic order streams (`SIMULATION_SEED=42`):

| Evaluation Metric | Description | Expected Outcome vs. FIFO |
|---|---|---|
| **Average Waiting Time** | Elapsed time from order creation to pick assignment | Significant reduction for multi-item and high-urgency orders |
| **Throughput** | Orders completed and dispatched per hour | Higher sustained throughput by eliminating packing congestion |
| **Picker Utilization** | Ratio of active picking time to idle transit time | Balanced distribution across zones, reducing picker crowding |
| **SLA Breach Rate** | Percentage of orders delivered past SLA deadline | Measurable drop in SLA breaches due to dynamic urgency prioritization |
| **Packing Bottleneck** | Queue depth of totes awaiting packing benches | Smoothed packing queue via feedback-driven picking throttling |
| **LLM Fallback Rate** | Frequency of fallbacks to rule-based scoring under `llm_batch` | Monitored to verify 100% system availability despite API limits |

---

## Known Limitations & Roadmap

- [x] **Dynamic 5-Factor Priority Scorer:** Implemented with real-time weights.
- [x] **Autonomous A2A Multi-Agent Architecture:** Coordinated via Redis Pub/Sub.
- [x] **Standardized MCP Tool Layer:** 7 warehouse tools with HTTP invocation.
- [x] **Zero Firebase Lock-In:** Native WebSockets and REST APIs.
- [x] **Optional Gemini 2.5 Integration:** Decision commentary and safe batch re-ranking with 100% fail-safe fallback.
- [x] **Serverless Cloud Deployment:** Complete guides and blueprints for Vercel, Render, Neon, and Upstash.
- [ ] **Multi-Facility Orchestration:** Extend the digital twin across multiple dark stores and regional hubs.
- [ ] **Real-World WMS Connectors:** Ingest live feeds from Manhattan Associates, Blue Yonder, and SAP EWM.
- [ ] **Autonomous AGV Navigation:** Integrate with ROS2 (Robot Operating System) for automated guided vehicle dispatching.
- [ ] **Role-Based Access Control:** User authentication and role-based permissions for enterprise warehouse staff.

---

## Contributors

See [CONTRIBUTORS.md](./CONTRIBUTORS.md) for team member details and roles.

---

## License

This project is licensed under the MIT License — see the [LICENSE](./LICENSE) file for details.
