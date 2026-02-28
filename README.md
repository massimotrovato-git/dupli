# Dupli-Clone v0.1 (2-day build)
This repository is a **production-leaning scaffold** for a Duplikium-like copier:
- HTTPS via Nginx
- MFA via Keycloak (TOTP)
- OIDC auth handled by oauth2-proxy (FastAPI trusts headers)
- PostgreSQL + Redis
- FastAPI admin UI (web) + API
- Telegram ingest worker (Telethon) -> TradeIntents
- Execution workers with pluggable executors (cTrader + MT5 gateway)

## What is included (v0.1)
✅ Web access over HTTPS + MFA  
✅ RBAC (Admin/Operator/Viewer) via Keycloak roles/groups  
✅ CRUD for PropFirms, Accounts, Masters, CopySets, RiskProfiles, RuleSets  
✅ Telegram ingest -> normalized TradeIntent records  
✅ Rule evaluation v0.1: weekend blocks + manual "NEWS_RED" blocks (per Prop)  
✅ Execution pipeline: intents -> per-account jobs (Redis) -> executor stubs + MT5 gateway client

## What is NOT fully implemented in v0.1 (needs hardening)
- Full cTrader Open API integration (place/modify/partial/BE for all order types)
- Full MT5 terminal farm + EA bridge (this repo includes the gateway skeleton + protocol)
- Economic calendar provider integration for "red news" (v0.1 supports manual blocks you set in UI)
- Deep anti-desync reconciliation logic (v0.1 stores mappings; periodic reconciler is stubbed)

## Quick start (Linux CORE)
1) Copy `.env.example` to `.env` and fill values.
2) Start:
```bash
docker compose up -d --build
```
3) Open:
- https://YOUR_DOMAIN (oauth2-proxy -> app)
- https://YOUR_DOMAIN/auth (oauth2-proxy status)
- Keycloak Admin: http://SERVER_IP:8081 (behind firewall / or bind to localhost)

## Keycloak setup
This repo ships an import realm: `infra/keycloak/realm-export.json`
- Realm: `dupli`
- Clients: `dupli-app` (confidential), `oauth2-proxy` (confidential)
- Users: create in Keycloak admin console, enforce **Required Action: Configure OTP**
- Roles: `admin`, `operator`, `viewer`

## MT5 Gateway (Windows)
See `windows/mt5-gateway/README.md`
Run as a Windows Service (nssm) or Task Scheduler.
Linux CORE talks to it via `MT5_GATEWAY_URL`.

## Security note
- oauth2-proxy is configured to only trust requests coming through Nginx.
- Set firewall to allow:
  - 80/443 to Nginx
  - 8081 Keycloak admin only from your IP or localhost
  - MT5 gateway port only from CORE server IP

