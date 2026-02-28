# Dupli – RBAC & Security Policy

## Overview

Dupli uses **Keycloak** as identity provider with **OIDC** protocol.
Authentication is handled by **oauth2-proxy** sitting between Nginx and the FastAPI backend.
The API trusts the headers set by oauth2-proxy (`X-Auth-Request-Preferred-Username`, `X-Auth-Request-Groups`).

---

## Roles

| Role | Description | Permissions |
|------|-------------|-------------|
| **admin** | Platform administrator | Full CRUD on all entities, user management (via Keycloak), queue trade intents, view all logs, manage risk profiles and rule sets |
| **operator** | Operations user | CRUD on PropFirms, Accounts, Masters, CopySets, RiskProfiles; queue trade intents; view execution logs |
| **viewer** | Read-only user | View PropFirms, Accounts, Masters, CopySets, TradeIntents, ExecutionLogs |

### Permission Matrix

| Endpoint | admin | operator | viewer |
|----------|-------|----------|--------|
| `GET  /api/props` | R | R | R |
| `POST /api/props` | W | W | - |
| `GET  /api/accounts` | R | R | R |
| `POST /api/accounts` | W | W | - |
| `POST /api/masters` | W | W | - |
| `POST /api/copysets` | W | W | - |
| `POST /api/copysets/slaves` | W | W | - |
| `GET  /api/trade_intents` | R | R | R |
| `POST /api/trade_intents/{id}/queue` | X | X | - |
| `POST /api/risk_profiles` | W | W | - |
| `GET  /api/health` | R | R | R |

Legend: **R** = read, **W** = write/create, **X** = execute action, **-** = forbidden (HTTP 403)

---

## Master / Slave Model

```
Master (signal source)
  |
  +-- CopySet (grouping)
        |
        +-- CopySetSlave -> Account (execution target)
              |
              +-- PropFirm (rules: weekend block, news block)
              +-- RiskProfile (lot sizing: fixed_lot, percent_equity, risk_per_trade)
```

### Signal Flow

1. **Master** receives a trade signal (from Telegram, cTrader, or manual entry)
2. Signal is stored as a **TradeIntent** (`status=NEW`)
3. An operator or automation queues the intent (`status=QUEUED`)
4. The **Worker** picks up the job from Redis
5. For each active **CopySet** linked to the Master:
   - For each **CopySetSlave** in the CopySet:
     - Check **PropFirm rules** (weekend block, news_red block)
     - Apply **RiskProfile** (lot sizing)
     - Execute via the appropriate **Executor** (cTrader or MT5 gateway)
     - Log result in **ExecutionLog**

### Security Boundaries

- **Masters** are created by admin/operator only
- **CopySets** link a master to slave accounts – admin/operator only
- **Accounts** contain platform credentials (external_id) – admin/operator only
- **Viewers** can only observe; they cannot trigger any trade execution

---

## Groups

Groups provide an easy way to manage role assignments in Keycloak.

| Group | Mapped Role | Use Case |
|-------|-------------|----------|
| `admins` | `admin` | Platform administrators |
| `operators` | `operator` | Traders / operations team |
| `viewers` | `viewer` | Monitoring / compliance |

Assign users to groups in Keycloak Admin Console → Users → [user] → Groups tab.

---

## OIDC Scopes & Token Claims

### Client Scope: `dupli-roles`

This custom scope is attached to the `oauth2-proxy` client and includes three protocol mappers:

| Mapper | Type | Claim Name | Description |
|--------|------|------------|-------------|
| `realm-roles` | `oidc-usermodel-realm-role-mapper` | `roles` | Array of realm roles assigned to the user |
| `groups` | `oidc-group-membership-mapper` | `groups` | Array of group names the user belongs to |
| `preferred_username` | `oidc-usermodel-attribute-mapper` | `preferred_username` | Username string |

### Example ID Token Payload

```json
{
  "sub": "a1b2c3d4-...",
  "preferred_username": "trader1",
  "email": "trader1@example.com",
  "roles": ["operator"],
  "groups": ["/operators"],
  "iss": "https://YOUR_DOMAIN/realms/dupli",
  "aud": "oauth2-proxy",
  "exp": 1700000000
}
```

### How oauth2-proxy Uses Claims

oauth2-proxy extracts the claims and forwards them as HTTP headers to the FastAPI backend:

| Header | Source Claim |
|--------|-------------|
| `X-Auth-Request-Preferred-Username` | `preferred_username` |
| `X-Auth-Request-Email` | `email` |
| `X-Auth-Request-Groups` | `groups` (comma-separated) |

The FastAPI `auth.py` module parses these headers and builds a `UserCtx` object with the username and roles.

---

## Security Hardening Checklist

- [ ] **TOTP/MFA**: Enforce `CONFIGURE_TOTP` as required action for all users
- [ ] **Brute-force protection**: Enabled in realm (failureFactor=5, lockout=60s)
- [ ] **Token lifetimes**: Access token = 5 min, SSO session idle = 30 min, SSO max = 10 h
- [ ] **HTTPS only**: Nginx terminates TLS; `OAUTH2_PROXY_COOKIE_SECURE=true` in production
- [ ] **Firewall**: Port 8081 (Keycloak admin) only from trusted IPs
- [ ] **No direct API access**: All API requests must pass through Nginx → oauth2-proxy
- [ ] **Secrets rotation**: Rotate `OAUTH2_PROXY_CLIENT_SECRET`, `OAUTH2_PROXY_COOKIE_SECRET`, and DB passwords regularly
- [ ] **No registration**: `registrationAllowed: false` in realm config
- [ ] **SSL required**: `sslRequired: "external"` in realm config
