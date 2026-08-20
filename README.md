<p align="center">
  <img src="assets/A2A_Digital_Twin_Poster.png" alt="A2A Digital Twin banner" width="100%">
</p>

# A2A Digital Twin — Warehouse

**A simulated warehouse digital twin that replaces static FIFO queues with a dynamic, negotiated priority engine — coordinated by autonomous agents talking to each other over A2A, with state accessed through an MCP-style tool layer.**

Built by Team **[Brute Force 6](./CONTRIBUTORS.md)**.

---

## Table of Contents

- [Problem](#problem)
- [Solution](#solution)
- [Architecture](#architecture)
- [Agents](#agents)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup](#setup)
- [Usage](#usage)
- [Validation Targets](#validation-targets)
- [Current Phase](#current-phase)
- [Phase Plan](#phase-plan)
- [Known Limitations / Future Scope](#known-limitations--future-scope)
- [License](#license)

---

## Problem

Quick-commerce dark stores run on fixed FIFO order queues. A FIFO queue treats every order the same regardless of SLA risk, order value, item availability, or current picker load — so a five-item order that just missed its SLA window waits behind nine single-item orders with hours of slack. The result is avoidable SLA breaches, uneven picker utilization, and packing-stage bottlenecks that a smarter scheduling policy could avoid entirely.

## Solution

A2A Digital Twin is a **simulated warehouse orchestration prototype** that swaps the static FIFO queue for a **dynamic priority engine**, driven by specialized agents that negotiate over which order gets worked next:

1. Orders arrive through an ingestion API and are handed to the **Order Coordinator Agent**.
2. The Coordinator scores and re-scores orders continuously against a **dynamic priority queue** — factoring in SLA risk, inventory state, and current pick/pack load.
3. The **Inventory**, **Picking**, and **Packing & Dispatch** agents negotiate task assignment over an **A2A message bus**, each exposing and consuming warehouse state through a standardized **MCP-style tool layer**.
4. Every decision, negotiation, and state change streams to a **live dashboard** over WebSockets, so the priority queue, zone heatmap, agent activity, and negotiation history are all visible in real time.
5. The same synthetic order stream can be replayed against **FIFO** and against the **dynamic priority queue**, so the two policies are compared on identical workloads rather than anecdotally.

The scheduling logic is intentionally **pure rule-based** — no LLM sits in the negotiation or scoring decision path. An inert `explain_decision()` hook is left in place for a possible future Claude-based dashboard commentary layer, but it plays no role in any actual decision today.

## Architecture

```text
Customer / Order Stream
  -> Order Ingestion API
  -> Order Coordinator Agent
  -> Dynamic Priority Queue
  -> Inventory Agent / Picking Agent / Packing and Dispatch Agent
  -> A2A Message Bus
  -> MCP Tool Layer
  -> PostgreSQL + Redis + Simulation
  -> WebSocket Events
  -> Live Dashboard
```

**A2A** handles agent-to-agent messaging, task delegation, negotiation, and context propagation.
**MCP-style tools** handle standardized access to warehouse state, infrastructure, and data — no agent talks to Postgres or Redis directly.

## Agents

| Agent | Responsibility |
|---|---|
| Order Coordinator Agent | Scores incoming orders, maintains the dynamic priority queue, delegates work |
| Inventory Agent | Tracks stock levels and availability, answers reservation requests |
| Picking Agent | Claims and executes pick tasks, reports picker utilization and load |
| Packing and Dispatch Agent | Finalizes orders for dispatch, surfaces packing-stage bottlenecks |

Dock-related code, where present, is optional and is never required for the primary MVP workflow.

## Tech Stack

| Layer | Tool |
|---|---|
| Backend framework | FastAPI (`backend/core`) |
| Domain logic | `backend/domains/warehouse` |
| Agent messaging | Custom A2A protocol / message bus |
| State access | MCP-style tool registry |
| Persistence | PostgreSQL 16 |
| Live state, queues, pub/sub | Redis 7 |
| Frontend | Next.js (`frontend/src/core` shared + `frontend/src/domains/warehouse` domain views) |
| Real-time updates | WebSocket |
| Simulation | Poisson-based synthetic order generator, seeded for reproducibility |

## Project Structure

```text
a2a-digital-twin/
├── backend/
│   ├── core/
│   │   ├── a2a/
│   │   │   ├── __init__.py
│   │   │   ├── message_bus.py
│   │   │   └── protocol.py
│   │   ├── mcp/
│   │   │   ├── __init__.py
│   │   │   └── registry.py
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   └── base.py
│   │   ├── queue_engine/
│   │   │   ├── __init__.py
│   │   │   └── base.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py
│   │   │   ├── message.py
│   │   │   ├── negotiation.py
│   │   │   └── task.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── health.py
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   │
│   ├── domains/
│   │   ├── __init__.py
│   │   └── warehouse/
│   │       ├── __init__.py
│   │       ├── agents/
│   │       │   ├── __init__.py
│   │       │   ├── order_agent.py
│   │       │   ├── inventory_agent.py
│   │       │   ├── picking_agent.py
│   │       │   ├── packing_agent.py
│   │       │   └── dock_agent.py
│   │       ├── services/
│   │       │   └── __init__.py
│   │       ├── simulation/
│   │       │   ├── __init__.py
│   │       │   ├── order_generator.py
│   │       │   └── seeder.py
│   │       ├── models/
│   │       │   ├── __init__.py
│   │       │   ├── order.py
│   │       │   ├── inventory_item.py
│   │       │   └── dock.py
│   │       ├── queue_engine/
│   │       │   ├── __init__.py
│   │       │   └── scorer.py
│   │       └── api/
│   │           ├── __init__.py
│   │           └── routes.py
│   │
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── core/
│   │   │   ├── components/
│   │   │   ├── dashboard/
│   │   │   └── negotiation-viewer/
│   │   ├── domains/
│   │   │   └── warehouse/
│   │   │       ├── components/
│   │   │       └── views/
│   │   └── app/
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json
│   └── next.config.js
│
├── docker-compose.yml
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

This project is scoped to a single domain — **warehouse fulfillment**. There is no airport domain, no second-domain UI, and no airport phase in the plan below.

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/Maharshi-Paul/warehouse-a2a-digital-twin.git
cd warehouse-a2a-digital-twin
```

### 2. Start infrastructure

```bash
docker compose up -d postgres redis
```

Validate the compose configuration at any point with:

```bash
docker compose config
```

### 3. Configure environment

Copy `.env.example` to `.env` for local development and adjust values as needed. **Do not commit secrets.**

Key defaults:

| Variable | Default |
|---|---|
| `DOMAIN` | `warehouse` |
| `DATABASE_URL` | `postgresql+asyncpg://wdt_user:wdt_pass@localhost:5432/warehouse_twin` |
| `REDIS_URL` | `redis://localhost:6379/0` |
| `QUEUE_TICK_SECONDS` | `2.0` |
| `SIMULATION_SEED` | `42` |
| `LLM_PROVIDER` | `none` |

### 4. Install dependencies

```bash
pip install -r backend/requirements.txt
cd frontend && npm install
```

### 5. Run the backend

From `backend/`:

```bash
uvicorn core.main:app --reload
```

On startup this creates the database tables, seeds synthetic simulation data (zones, SKUs, shelves, workers, packing stations, dock doors), connects to Redis, and starts all warehouse agents. Once ready:

- API: http://localhost:8000
- Docs (Swagger UI): http://localhost:8000/docs
- WebSocket: ws://localhost:8000/ws/live

### 6. Run the frontend

From `frontend/`:

```bash
npm run dev
```

- Local: http://localhost:3000

### Windows notes

- `wsl --install` requires a reboot before Docker Desktop's WSL2 backend can start; if `docker ps` fails with a 500 error or "cannot find the file specified" right after installing WSL, reboot and relaunch Docker Desktop, then retry.
- If `npm run dev` fails with `running scripts is disabled on this system` in PowerShell, either run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` from an elevated PowerShell, or run the command from `cmd.exe` instead, where this restriction doesn't apply.
- To stop, `Ctrl+C` in each server's terminal, then `docker-compose down` (or `docker compose down`) from the project root to stop Postgres and Redis.

## Usage

Once the backend and frontend are running, open the frontend to watch the live dashboard — real-time KPIs, the dynamic priority queue, a zone heatmap, an agent activity feed, a negotiation viewer, worker status, and packing/dock monitors, all driven over WebSocket. Use the **Seed DB** and **Start Sim** controls on the dashboard to populate data and kick off the synthetic order stream.

To compare scheduling policies, replay the same synthetic workload (same `SIMULATION_SEED`) once under FIFO and once under the dynamic priority queue, and diff the resulting metrics.

## Validation Targets

KPI improvements are only claimed once they're measured by actual simulations against the same workload — not asserted ahead of the data. Target metrics from the source design documents:

- Average waiting time reduction
- Throughput increase
- Picker utilization improvement
- SLA breach reduction
- Packing bottleneck reduction

## Current Phase

**Phase 10: Polish — Complete.**

All phases are implemented. The backend runs under `backend/core` (framework) + `backend/domains/warehouse` (business logic). The frontend uses a modular architecture under `frontend/src/core` (shared components, hooks, types) + `frontend/src/domains/warehouse` (domain views and components).

## Phase Plan

| Phase | Description |
|---|---|
| 0 | Scaffold |
| 1 | Core foundation |
| 2 | Core engine |
| 3 | Core app |
| 4 | Warehouse data |
| 5 | Warehouse agents |
| 6 | Warehouse queue engine and services |
| 7 | Warehouse simulation and API |
| 8 | Frontend core |
| 9 | Warehouse frontend |
| 10 | Polish |

## Known Limitations / Future Scope

- Scheduling is pure rule-based today; the `explain_decision()` hook exists but is inert — no LLM sits in the decision path
- All workloads are synthetic — there is no external/real-world test data source yet
- Single-domain (warehouse) only, though the project is intended to generalize to additional domains (e.g. airports) in a future iteration
- Dock-related code, where present, is optional and not exercised by the primary MVP path

## License

MIT. See `LICENSE`.
