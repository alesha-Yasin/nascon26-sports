# NaSCon '26 Sports Platform

## Quick Start

```bash
# 1. Set your DAY1_SALT
export DAY1_SALT=your-salt-here

# 2. Start the entire stack
DAY1_SALT=$DAY1_SALT docker compose up -d --build

# 3. Wait for health check (polls every 2s, max 120s)
curl http://localhost:8080/health
# → {"status":"ok"}

# 4. Reset and seed baseline data
curl -X POST http://localhost:8080/audit/v1/reset
```

## Demo Accounts

| Role | Email | Password |
|------|-------|----------|
| Platform Super-Admin | admin@nascon.test | Nascon@26 |
| League Organizer | organizer@nascon.test | Nascon@26 |
| Club Manager | manager@nascon.test | Nascon@26 |
| Player | player@nascon.test | Nascon@26 |
| General Viewer | viewer@nascon.test | Nascon@26 |

## Architecture

```
docker-compose.yml
├── api (FastAPI on :8080)
│   ├── POST /health
│   ├── POST /audit/v1/reset
│   ├── POST /audit/v1/sports
│   ├── POST /audit/v1/fixtures
│   ├── POST /audit/v1/leagues
│   ├── POST /audit/v1/events
│   ├── GET  /audit/v1/score/{match_id}
│   ├── GET  /audit/v1/standings/{league_id}
│   ├── POST /audit/v1/roster/setup
│   ├── POST /audit/v1/roster/transfer
│   ├── GET  /audit/v1/roster/history/{player_id}
│   ├── POST /audit/v1/checkout
│   ├── GET  /audit/v1/inventory/{variant_id}
│   ├── POST /audit/v1/rbac-matrix
│   ├── /audit/v1/rbac/* (7 probe routes)
│   ├── GET  /api/v1/ping
│   └── POST /audit/v1/offline-sync
├── db  (PostgreSQL 16)
├── redis (Redis 7)
└── minio (MinIO object store)
```

## Running Tests

```bash
cd backend
pip install -r requirements.txt
./run_tests.sh
```

## Environment Variables

See `.env.example` for all required variables.

## GitHub Repository

https://github.com/alesha-Yasin/nascon26-sports
