# 🏭 Smart Agent-to-Agent, Queue-Aware Digital Twin for Warehouse Logistics

> AI-Powered Multi-Agent Orchestration System replacing static FIFO queues with dynamic, SLA-aware priority scoring.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker Desktop (for PostgreSQL & Redis)

### 1. Start Infrastructure
```bash
docker-compose up -d
```

### 2. Start Backend
```bash
cd backend
pip install -r requirements.txt
python -m app.main
```

### 3. Seed & Simulate
```bash
# Seed warehouse data (200 SKUs, 10 workers, etc.)
curl -X POST http://localhost:8000/api/simulation/seed

# Start Poisson order generator
curl -X POST http://localhost:8000/api/simulation/start
```

### 4. Start Frontend
```bash
cd frontend
npm install
npm run dev
```

### 5. Explore
- **API Docs**: http://localhost:8000/docs
- **Dashboard**: http://localhost:3000
- **WebSocket**: ws://localhost:8000/ws/live

## 🏗️ Architecture

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

## 📊 Priority Scoring Formula

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

## 🔧 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/orders` | Paginated order list by priority |
| GET | `/api/queue` | Current priority queue ranking |
| GET | `/api/warehouse/status` | Zone, worker, station status |
| GET | `/api/warehouse/kpis` | Real-time KPIs |
| GET | `/api/agents/logs` | A2A communication audit trail |
| POST | `/api/simulation/seed` | Seed warehouse data |
| POST | `/api/simulation/start` | Start order generator |
| POST | `/api/simulation/stop` | Stop order generator |
| GET | `/mcp/tools` | List MCP tools |
| POST | `/mcp/invoke` | Invoke MCP tool |

## 📁 Tech Stack

- **Backend**: Python 3.11, FastAPI, async SQLAlchemy, asyncpg
- **Agents**: Custom A2A protocol over Redis Pub/Sub
- **State**: PostgreSQL 16 + Redis 7
- **Frontend**: Next.js 14, Tailwind CSS, WebSockets
- **Infra**: Docker Compose
