# Dupli-Clone v0.1

A **production-leaning scaffold** for a Duplikium-like trade copier platform.

## Architecture

```
                  +-----------+
  Browser ------->|   Nginx   |:80/443
                  +-----+-----+
                        |
                  +-----v--------+       +------------+
                  | oauth2-proxy |<----->|  Keycloak   |:8081
                  +-----+--------+       +------------+
                        |
                  +-----v-----+    +-------+    +-----------+
                  |  FastAPI   |<-->| Redis |<-->|  Worker   |
                  |   (API)    |    +-------+    +-----------+
                  +-----+------+
                        |
                  +-----v------+
                  | PostgreSQL |
                  +------------+

                  +------------+
                  |  Telegram  |  (ingest -> TradeIntents)
                  +------------+
```

| Service | Descrizione |
|---------|-------------|
| **nginx** | Reverse-proxy con terminazione TLS, redirect HTTP->HTTPS |
| **keycloak** | Identity provider OIDC, MFA (TOTP), ruoli RBAC |
| **oauth2-proxy** | Autentica le richieste via OIDC prima di inoltrarle all'API |
| **api** | FastAPI - CRUD PropFirms, Accounts, Masters, CopySets, RiskProfiles, RuleSets, UI minimale |
| **worker** | RQ worker - esegue i TradeIntent (executor stubs cTrader + MT5 gateway) |
| **telegram** | Telethon client - legge segnali da un canale Telegram e crea TradeIntent |
| **postgres** | Database relazionale (PostgreSQL 16) |
| **redis** | Broker code di lavoro (RQ) |

### Cosa include v0.1

- Accesso web via HTTPS + MFA
- RBAC (Admin / Operator / Viewer) tramite ruoli Keycloak
- CRUD per PropFirms, Accounts, Masters, CopySets, RiskProfiles, RuleSets
- Telegram ingest -> record TradeIntent normalizzati
- Valutazione regole v0.1: blocco weekend + blocco manuale "NEWS_RED" (per Prop)
- Pipeline esecuzione: intents -> job per account (Redis) -> executor stubs + MT5 gateway client

### Cosa NON e' completo in v0.1

- Integrazione completa cTrader Open API
- MT5 terminal farm + EA bridge (incluso solo lo skeleton del gateway)
- Provider calendario economico per "red news" (v0.1 supporta blocchi manuali via UI)
- Logica anti-desync profonda (v0.1 memorizza mappings; il reconciler periodico e' stub)

---

## Prerequisiti

- [Docker](https://docs.docker.com/get-docker/) >= 24.0
- [Docker Compose](https://docs.docker.com/compose/install/) >= 2.20 (incluso con Docker Desktop)
- `openssl` (per generare certificati self-signed in locale)
- Git

---

## Avvio locale (step-by-step)

### 1. Clona il repository

```bash
git clone https://github.com/massimotrovato-git/dupli.git
cd dupli
```

### 2. Crea il file `.env`

```bash
cp .env.example .env
```

Modifica `.env` con i tuoi valori. Per sviluppo locale i default funzionano, ma **devi** almeno:

| Variabile | Valore consigliato (locale) | Note |
|-----------|----------------------------|------|
| `APP_BASE_URL` | `https://localhost` | |
| `APP_SECRET_KEY` | una stringa random | `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `POSTGRES_PASSWORD` | una password a scelta | |
| `KEYCLOAK_ADMIN_PASSWORD` | una password a scelta | per accedere alla console admin Keycloak |
| `OAUTH2_PROXY_CLIENT_SECRET` | vedi realm-export.json | il secret del client `oauth2-proxy` nel realm Keycloak |
| `OAUTH2_PROXY_COOKIE_SECRET` | stringa base64 32 byte | `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `OAUTH2_PROXY_REDIRECT_URL` | `https://localhost/oauth2/callback` | deve corrispondere al redirect URI in Keycloak |
| `OAUTH2_PROXY_COOKIE_SECURE` | `false` | **solo in locale** con certificati self-signed |

### 3. Genera certificati TLS self-signed (solo sviluppo locale)

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout infra/nginx/certs/privkey.pem \
  -out infra/nginx/certs/fullchain.pem \
  -subj "/CN=localhost"
```

> **Nota**: il browser mostrera' un avviso di certificato non attendibile. Accetta l'eccezione per procedere.

### 4. Avvia tutti i servizi

```bash
docker compose up -d --build
```

La prima volta il build scarica le immagini base e installa le dipendenze Python (circa 2-5 minuti).

Verifica che tutti i container siano in esecuzione:

```bash
docker compose ps
```

Tutti i servizi devono risultare `Up` oppure `Up (healthy)`.

### 5. Verifica i log (opzionale)

```bash
# Tutti i servizi
docker compose logs -f

# Solo un servizio specifico
docker compose logs -f api
docker compose logs -f keycloak
```

### 6. Configura un utente in Keycloak

1. Apri la console admin Keycloak: **http://localhost:8081**
2. Accedi con `KEYCLOAK_ADMIN` / `KEYCLOAK_ADMIN_PASSWORD` (default: `admin` / `admin_change_me`)
3. Seleziona il realm **dupli** (menu a tendina in alto a sinistra)
4. Vai su **Users** -> **Add user**
5. Compila username, email, first/last name
6. Nella tab **Credentials** imposta una password (disabilita "Temporary")
7. Nella tab **Role mapping** assegna uno dei ruoli: `admin`, `operator`, o `viewer`
8. *(Opzionale)* Per abilitare MFA/TOTP: vai su **Required Actions** e seleziona **Configure OTP**

### 7. Accedi all'applicazione

| URL | Descrizione |
|-----|-------------|
| **https://localhost** | App principale (via oauth2-proxy -> FastAPI) |
| **https://localhost/docs** | Swagger UI (documentazione API interattiva) |
| **https://localhost/ui** | UI web minimale |
| **http://localhost:8081** | Console admin Keycloak |

> Al primo accesso verrai rediretto a Keycloak per il login. Usa le credenziali dell'utente creato al passo 6.

---

## Comandi utili

```bash
# Avvia in foreground (vedi i log in tempo reale)
docker compose up --build

# Ferma tutti i servizi
docker compose down

# Ferma e rimuovi anche i volumi (ATTENZIONE: cancella i dati!)
docker compose down -v

# Ricostruisci un singolo servizio
docker compose up -d --build api

# Accedi alla shell di un container
docker compose exec api bash
docker compose exec postgres psql -U dupli -d dupli
```

---

## Struttura del progetto

```
dupli/
├── docker-compose.yml          # Orchestrazione di tutti i servizi
├── .env.example                # Template variabili d'ambiente
├── .env                        # Variabili d'ambiente (non committare!)
├── services/
│   ├── api/                    # FastAPI backend
│   │   ├── Dockerfile
│   │   └── app/
│   │       ├── main.py         # Endpoint e UI
│   │       ├── models.py       # Modelli SQLAlchemy
│   │       ├── schemas.py      # Pydantic schemas
│   │       ├── auth.py         # Autenticazione (header oauth2-proxy)
│   │       ├── db.py           # Connessione database
│   │       ├── queue.py        # Coda Redis (RQ)
│   │       └── rules.py        # Regole di trading
│   ├── worker/                 # RQ execution worker
│   │   ├── Dockerfile
│   │   └── worker/
│   │       ├── run.py          # Entrypoint worker
│   │       ├── jobs.py         # Job di esecuzione trade
│   │       ├── executors.py    # Executor stubs (cTrader, MT5)
│   │       ├── models.py
│   │       ├── db.py
│   │       └── rules.py
│   └── telegram/               # Telegram signal ingest
│       ├── Dockerfile
│       └── telegram_ingest/
│           ├── run.py          # Telethon client
│           ├── parser.py       # Parser segnali
│           ├── models.py
│           └── db.py
├── infra/
│   ├── nginx/
│   │   ├── nginx.conf          # Config principale Nginx
│   │   ├── conf.d/app.conf     # Virtual host (TLS + proxy)
│   │   └── certs/              # Certificati TLS (fullchain.pem, privkey.pem)
│   ├── keycloak/
│   │   └── realm-export.json   # Realm Keycloak pre-configurato
│   └── postgres/
│       └── init.sql            # Script inizializzazione DB
└── windows/
    └── mt5-gateway/            # Gateway MT5 per Windows (skeleton)
        ├── README.md
        └── mt5_gateway/app.py
```

---

## Deploy in produzione

Per il deploy su un server reale:

1. Sostituisci i certificati self-signed con certificati reali (es. Let's Encrypt)
2. Aggiorna `.env`:
   - `APP_ENV=prod`
   - `APP_BASE_URL=https://tuo-dominio.com`
   - `OAUTH2_PROXY_REDIRECT_URL=https://tuo-dominio.com/oauth2/callback`
   - `OAUTH2_PROXY_COOKIE_SECURE=true`
   - Password sicure per Postgres e Keycloak
3. Aggiorna `infra/keycloak/realm-export.json` con il redirect URI corretto
4. Configura il firewall:
   - Porta 80/443 aperte (Nginx)
   - Porta 8081 (Keycloak admin) solo da localhost o IP trusted
   - Porta MT5 gateway solo dall'IP del server CORE

---

## MT5 Gateway (Windows)

Vedi [`windows/mt5-gateway/README.md`](windows/mt5-gateway/README.md).

Il gateway va eseguito su una macchina Windows con MT5 installato. Il server Linux comunica con esso tramite la variabile `MT5_GATEWAY_URL`.

---

## Sicurezza

- oauth2-proxy accetta solo richieste inoltrate da Nginx (header `X-Forwarded-Proto`)
- Non esporre la porta 8081 (Keycloak admin) su internet
- Non committare il file `.env` nel repository
- In produzione usa sempre `OAUTH2_PROXY_COOKIE_SECURE=true`

