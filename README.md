# Warehouse A2A Digital Twin

AI-powered queue management and warehouse orchestration prototype for quick-commerce dark stores.

This project is focused on one domain only:

- Warehouse fulfillment

It does not implement an airport domain or any second-domain UI.

## Objective

Build a simulated warehouse digital twin that coordinates specialized agents through A2A communication, accesses state through an MCP-style tool layer, and compares FIFO scheduling against a dynamic priority queue using identical synthetic workloads.

The MVP centers on four warehouse agents:

- Order Coordinator Agent
- Inventory Agent
- Picking Agent
- Packing and Dispatch Agent

Dock-related code, if present, is optional and must not be required for the primary MVP workflow.

## Architecture Target

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

A2A is responsible for agent-to-agent messaging, task delegation, negotiation, and context propagation.

MCP-style tools are responsible for standardized access to warehouse state, infrastructure, and data.

## Current Phase

Phase 0: Scaffold.

The repository now contains the documented package skeleton for the future modular implementation under `backend/core` and `backend/domains/warehouse`. The earlier `backend/app` implementation remains in place and should be audited and migrated phase by phase rather than overwritten blindly.

## Project Structure

```text
warehouse-a2a-digital-twin-private/
  backend/
    app/                         Existing implementation retained for audit/migration
    core/
      a2a/
      agents/
      api/
      mcp/
      models/
      queue_engine/
    domains/
      warehouse/
        agents/
        api/
        models/
        queue_engine/
        services/
        simulation/
    requirements.txt
  frontend/
    src/
      app/
      core/
        components/
        dashboard/
        negotiation-viewer/
      domains/
        warehouse/
          components/
          views/
  assets/
  docker-compose.yml
  .env.example
  .gitignore
  LICENSE
  README.md
```

## Infrastructure

The local infrastructure uses:

- PostgreSQL 16 for persistent transactional data
- Redis 7 for live state, queues, pub/sub, and transient simulation state

Start infrastructure:

```bash
docker compose up -d postgres redis
```

Validate compose configuration:

```bash
docker compose config
```

## Environment

Copy `.env.example` to `.env` for local development and adjust values as needed. Do not commit secrets.

Key defaults:

- `DOMAIN=warehouse`
- `DATABASE_URL=postgresql+asyncpg://wdt_user:wdt_pass@localhost:5432/warehouse_twin`
- `REDIS_URL=redis://localhost:6379/0`
- `QUEUE_TICK_SECONDS=2.0`
- `SIMULATION_SEED=42`
- `LLM_PROVIDER=none`

## Phase Plan

The project should be implemented one phase at a time:

1. Phase 0: Scaffold
2. Phase 1: Core foundation
3. Phase 2: Core engine
4. Phase 3: Core app
5. Phase 4: Warehouse data
6. Phase 5: Warehouse agents
7. Phase 6: Warehouse queue engine and services
8. Phase 7: Warehouse simulation and API
9. Phase 8: Frontend core
10. Phase 9: Warehouse frontend
11. Phase 10: Polish

There is no airport phase.

## Validation Targets

Do not claim KPI improvements until they are measured by actual simulations against the same workload.

Target metrics from the source documents include:

- Average waiting time reduction
- Throughput increase
- Picker utilization improvement
- SLA breach reduction
- Packing bottleneck reduction

## License

MIT. See `LICENSE`.
