<p align="center">
  <!-- Replace with your own banner image in assets/ -->
  <img src="assets/warehouse_banner.png" alt="Warehouse A2A Digital Twin banner" width="100%">
</p>

# Warehouse A2A Digital Twin

**A smart, agent-to-agent, queue-aware digital twin for warehouse logistics — replacing static FIFO queues with AI-orchestrated, SLA-aware priority scoring.**

Built by [Maharshi-Paul](https://github.com/Maharshi-Paul).

---

## Table of Contents

- [Problem](#problem)
- [Solution](#solution)
- [Architecture](#architecture)
- [Priority Scoring Formula](#priority-scoring-formula)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup](#setup)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Known Limitations / Future Scope](#known-limitations--future-scope)
- [License](#license)

---

## Problem

Traditional warehouse management systems rely on **static FIFO queues** — orders are processed in the order they arrive, with no regard for SLA deadlines, inventory availability, aisle congestion, or packing capacity. This leads to missed SLAs, idle workers waiting on stock, congested pick aisles, and an overall inability to adapt to real-time conditions on the warehouse floor. As order volumes scale, the gap between what a dumb queue can handle and what the operation actually needs widens dramatically.

## Solution

Warehouse A2A Digital Twin replaces the static queue with a **multi-agent orchestration system** where specialized AI agents — Order Coordinator, Inventory Agent, Picking Agent, Packing Agent, and Dock Agent — communicate via an **Agent-to-Agent (A2A) protocol over Redis Pub/Sub** and interact with warehouse infrastructure through the **Model Context Protocol (MCP)**.

A **Dynamic Priority Queue Engine** continuously re-scores every order using a weighted formula that accounts for:

- **SLA risk** — how close the order is to its deadline
- **Wait time** — how long the order has been queued
- **Inventory readiness** — fraction of items currently in stock
- **Aisle congestion** — inverse of current pick-path traffic
- **Packing capacity** — available packing station throughput

Orders are re-ranked in real time, and agents autonomously coordinate picking, packing, and dock assignment — ensuring the most urgent, actionable orders are always processed first.

## Architecture

```
┌──────────────┐     A2A (Redis Pub/Sub)     ┌──────────────┐
│   Order      │◄──────────────────────────►  │  Inventory   │
│ Coordinator  │                              │    Agent     │
│  (Master)    │        ┌──────────┐          └──────────────┘
└──────┬───────┘        │ Dynamic  │
       │                │ Priority │          ┌──────────────┐
       ▼                │  Queue   │◄────────►│   Picking    │
┌──────────────┐        │  Engine  │          │    Agent     │
│   Packing    │        └──────────┘          └──────────────┘
│    Agent     │
└──────┬───────┘        ┌──────────┐
       │                │   MCP    │
       ▼                │  Tools   │
┌──────────────┐        └──────────┘
│    Dock      │
│    Agent     │
└──────────────┘
```

**How agents communicate:**

| Layer | Protocol | Purpose |
|---|---|---|
| Agent ↔ Agent | A2A over Redis Pub/Sub | Real-time coordination, task handoffs, status broadcasts |
| Agent ↔ Warehouse | MCP (Model Context Protocol) | Tool invocation for inventory checks, zone queries, worker assignment |
| Client ↔ Server | REST + WebSocket | Dashboard updates, live KPI streaming |

## Priority Scoring Formula

```
Priority = w1·SLA_Risk + w2·Wait_Time + w3·Inventory_Readiness
         + w4·(1/Congestion) + w5·Packing_Capacity
```

| Weight | Component | Default | Description |
|--------|-----------|---------|-------------|
| w1 | SLA Risk | 0.35 | Urgency based on deadline proximity |
| w2 | Wait Time | 0.15 | Time spent in queue |
| w3 | Inventory | 0.25 | Fraction of items in stock |
| w4 | Congestion⁻¹ | 0.10 | Inverse aisle congestion |
| w5 | Packing | 0.15 | Available packing capacity |

## Tech Stack

| Layer | Tool |
|---|---|
| Backend | Python 3.11, FastAPI, async SQLAlchemy, asyncpg |
| Agent Protocol | Custom A2A protocol over Redis Pub/Sub |
| Queue Engine | Dynamic priority scorer (weighted multi-factor) |
| MCP Layer | Model Context Protocol for tool invocation |
| Database | PostgreSQL 16 |
| Message Broker | Redis 7 |
| Frontend | Next.js 14, Tailwind CSS, WebSockets |
| Infrastructure | Docker Compose |

## Project Structure

```
warehouse-a2a-digital-twin/
├── backend/
│   ├── app/
│   │   ├── a2a/                # A2A protocol — message bus, protocol defs
│   │   ├── agents/             # Specialized agents (order, inventory, picking, packing, dock)
│   │   ├── api/                # FastAPI route handlers
│   │   ├── mcp/                # MCP tool registry and invocation
│   │   ├── models/             # SQLAlchemy ORM models
│   │   ├── queue_engine/       # Dynamic priority queue scorer
│   │   ├── services/           # Business logic services
│   │   ├── simulation/         # Poisson order generator, warehouse seeder
│   │   ├── config.py           # App configuration
│   │   ├── database.py         # DB connection and session management
│   │   └── main.py             # FastAPI entry point
│   └── requirements.txt
├── frontend/
│   ├── src/                    # Next.js app source
│   ├── public/                 # Static assets
│   ├── package.json
│   └── ...
├── docker-compose.yml          # PostgreSQL + Redis containers
├── .env.example                # Environment variable template
├── LICENSE
└── README.md
```

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/Maharshi-Paul/warehouse-a2a-digital-twin.git
cd warehouse-a2a-digital-twin
```

### 2. Start infrastructure (PostgreSQL + Redis)

```bash
docker-compose up -d
```

### 3. Install backend dependencies and start the server

```bash
cd backend
pip install -r requirements.txt
python -m app.main
```

> **Note:** Make sure to copy `.env.example` to `.env` and update any values if needed before starting the backend.

### 4. Install frontend dependencies and start the dashboard

```bash
cd frontend
npm install
npm run dev
```

## Usage

### Seed & Simulate

Once the backend is running, seed the warehouse and start the order generator:

```bash
# Seed warehouse data (200 SKUs, 10 workers, zones, stations)
curl -X POST http://localhost:8000/api/simulation/seed

# Start Poisson order generator (continuous stream of orders)
curl -X POST http://localhost:8000/api/simulation/start

# Stop the order generator
curl -X POST http://localhost:8000/api/simulation/stop
```

### Explore

- **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs) — interactive Swagger UI
- **Dashboard**: [http://localhost:3000](http://localhost:3000) — live warehouse digital twin
- **WebSocket**: `ws://localhost:8000/ws/live` — real-time event stream

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/orders` | Paginated order list sorted by priority |
| GET | `/api/queue` | Current priority queue ranking |
| GET | `/api/warehouse/status` | Zone, worker, and station status |
| GET | `/api/warehouse/kpis` | Real-time KPIs (throughput, SLA compliance, etc.) |
| GET | `/api/agents/logs` | A2A communication audit trail |
| POST | `/api/simulation/seed` | Seed warehouse data |
| POST | `/api/simulation/start` | Start Poisson order generator |
| POST | `/api/simulation/stop` | Stop order generator |
| GET | `/mcp/tools` | List available MCP tools |
| POST | `/mcp/invoke` | Invoke an MCP tool |

## Known Limitations / Future Scope

- No persistent agent memory — agents are stateless between restarts
- Priority weights are static; adaptive/ML-driven weight tuning is a planned improvement
- Single-warehouse deployment only — multi-warehouse federation is future scope
- No authentication or RBAC on the API yet
- WebSocket dashboard does not persist historical data between sessions
- Simulation uses synthetic Poisson-distributed orders — integration with real WMS data feeds is planned

## License

MIT — see [LICENSE](./LICENSE)
