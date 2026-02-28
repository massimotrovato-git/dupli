# Dupli-Clone v0.1

Piattaforma di copy-trading che riceve segnali da Telegram, li normalizza e li replica su account MT5/cTrader.

- HTTPS via Nginx
- MFA via Keycloak (TOTP)
- OIDC auth gestita da oauth2-proxy (FastAPI legge gli header)
- PostgreSQL + Redis
- FastAPI admin UI (web) + API
- Telegram ingest (Telethon) -> TradeIntents
- Worker di esecuzione con executor pluggabili (cTrader + MT5 gateway)

## Architettura

| Servizio | Descrizione |
|---|---|
| **postgres** | Database PostgreSQL 16 |
| **redis** | Broker di code (RQ) e cache |
| **keycloak** | Identity provider (OIDC) |
| **oauth2-proxy** | Reverse-proxy di autenticazione davanti all'API |
| **api** | FastAPI - CRUD, UI minimale, endpoint di trade |
| **worker** | RQ worker - esecuzione asincrona dei trade intent |
| **telegram** | Ingest Telegram - parsing segnali e creazione trade intent |
| **nginx** | Reverse proxy TLS (HTTPS) |

## Cosa include (v0.1)

- Web access over HTTPS + MFA
- RBAC (Admin/Operator/Viewer) via ruoli/gruppi Keycloak
- CRUD per PropFirms, Accounts, Masters, CopySets, RiskProfiles, RuleSets
- Telegram ingest -> record TradeIntent normalizzati
- Rule evaluation v0.1: blocco weekend + blocchi manuali "NEWS_RED" (per Prop)
- Pipeline di esecuzione: intents -> job per-account (Redis) -> executor stub + client MT5 gateway

## Non ancora completo in v0.1

- Integrazione completa cTrader Open API
- MT5 terminal farm + EA bridge (presente solo lo skeleton del gateway)
- Integrazione provider calendario economico per "red news" (v0.1 supporta blocchi manuali)
- Logica di riconciliazione anti-desync (v0.1 salva i mapping; reconciler stubbed)

## Prerequisiti

- [Docker](https://docs.docker.com/get-docker/) >= 24
- [Docker Compose](https://docs.docker.com/compose/install/) >= 2.20 (plugin V2)
- Certificati TLS (`fullchain.pem` e `privkey.pem`) in `infra/nginx/certs/`

## Avvio rapido

### 1. Clona il repository

```bash
git clone https://github.com/massimotrovato-git/dupli.git
cd dupli
```

### 2. Configura le variabili d'ambiente

```bash
cp .env.example .env
```

Modifica `.env` con i valori appropriati. Le variabili principali da personalizzare:

| Variabile | Descrizione |
|---|---|
| `APP_BASE_URL` | URL pubblico (es. `https://copytrading.example.com`) |
| `APP_SECRET_KEY` | Chiave segreta dell'applicazione |
| `POSTGRES_PASSWORD` | Password del database |
| `KEYCLOAK_ADMIN_PASSWORD` | Password admin di Keycloak |
| `OAUTH2_PROXY_CLIENT_SECRET` | Secret del client OIDC (deve corrispondere a Keycloak) |
| `OAUTH2_PROXY_COOKIE_SECRET` | Secret per i cookie (32 byte, base64) |
| `OAUTH2_PROXY_REDIRECT_URL` | URL di callback OAuth2 (`https://<dominio>/oauth2/callback`) |
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | Credenziali API Telegram |
| `TELEGRAM_SOURCE_CHAT_ID` | ID numerico del canale sorgente |

### 3. Certificati TLS

Posiziona i certificati nella directory `infra/nginx/certs/`:

```bash
cp /path/to/fullchain.pem infra/nginx/certs/fullchain.pem
cp /path/to/privkey.pem   infra/nginx/certs/privkey.pem
```

### 4. Avvia lo stack

```bash
docker compose up -d --build
```

L'ordine di avvio e gestito automaticamente tramite `depends_on` e healthcheck:

```
postgres -> redis -> keycloak -> api -> oauth2-proxy -> nginx
                                  \-> worker
                                  \-> telegram
```

### 5. Verifica lo stato dei servizi

```bash
docker compose ps
```

Tutti i servizi devono risultare `healthy`. Per monitorare l'avvio:

```bash
docker compose logs -f
```

### 6. Accesso

- **Web UI**: `https://<APP_BASE_URL>/ui`
- **API Docs (Swagger)**: `https://<APP_BASE_URL>/docs`
- **Keycloak Admin**: `http://localhost:8081` (user/password da `.env`)

Il primo accesso richiede l'autenticazione tramite Keycloak. Crea un utente nel realm `dupli` e assegna uno dei ruoli: `admin`, `operator`, `viewer`.

## Keycloak setup

Il repo include un realm pre-configurato: `infra/keycloak/realm-export.json`
- Realm: `dupli`
- Clients: `oauth2-proxy` (confidential)
- Utenti: creare nella console admin di Keycloak, impostare **Required Action: Configure OTP**
- Ruoli: `admin`, `operator`, `viewer`

## Healthcheck

Ogni servizio del `docker-compose.yml` include un healthcheck per garantire avvii ordinati e monitoraggio continuo.

| Servizio | Tipo di check | Dettaglio |
|---|---|---|
| **postgres** | `pg_isready` | Verifica che PostgreSQL accetti connessioni |
| **redis** | `redis-cli ping` | Verifica che Redis risponda a PING |
| **keycloak** | HTTP `/health/ready` | Controlla l'endpoint di readiness di Keycloak |
| **api** | HTTP `/docs` | Verifica che FastAPI sia avviato e risponda |
| **oauth2-proxy** | HTTP `/ping` | Endpoint di liveness di oauth2-proxy |
| **worker** | Connessione Redis | Verifica che il worker possa raggiungere Redis |
| **telegram** | Connessione Redis | Verifica che il servizio possa raggiungere Redis |
| **nginx** | HTTP/HTTPS localhost | Verifica che Nginx risponda su porta 80 o 443 |

### Controllare lo stato di salute

```bash
# Stato di tutti i servizi
docker compose ps

# Dettaglio healthcheck di un singolo servizio
docker inspect --format='{{json .State.Health}}' dupli-api-1 | python3 -m json.tool

# Log di un servizio specifico
docker compose logs -f api
```

### Parametri healthcheck

Ogni healthcheck e configurato con:

- **interval**: frequenza del controllo (5-10s)
- **timeout**: tempo massimo per il check (3-5s)
- **retries**: tentativi prima di dichiarare `unhealthy` (10-30)
- **start_period**: grazia iniziale per l'avvio del servizio (dove necessario)

## MT5 Gateway (Windows)

Vedi `windows/mt5-gateway/README.md`.
Eseguire come Windows Service (nssm) o Task Scheduler.
Il CORE Linux comunica con esso tramite `MT5_GATEWAY_URL`.

## Sicurezza

- oauth2-proxy accetta solo richieste provenienti da Nginx.
- Configurare il firewall per consentire:
  - 80/443 verso Nginx
  - 8081 (Keycloak admin) solo dal proprio IP o localhost
  - Porta MT5 gateway solo dall'IP del server CORE

## Comandi utili

```bash
# Avvio in foreground (con log visibili)
docker compose up --build

# Stop di tutti i servizi
docker compose down

# Stop e rimozione volumi (ATTENZIONE: cancella i dati)
docker compose down -v

# Rebuild di un singolo servizio
docker compose up -d --build api

# Restart di un servizio
docker compose restart worker

# Visualizza i log di un servizio
docker compose logs -f telegram
```

## Struttura del progetto

```
dupli/
├── docker-compose.yml
├── .env.example
├── infra/
│   ├── keycloak/
│   │   └── realm-export.json      # Configurazione realm Keycloak
│   ├── nginx/
│   │   ├── nginx.conf             # Configurazione base Nginx
│   │   ├── conf.d/app.conf        # Virtual host HTTPS + OAuth2
│   │   └── certs/                 # Certificati TLS
│   └── postgres/
│       └── init.sql               # Script inizializzazione DB
└── services/
    ├── api/                       # FastAPI - CRUD e UI
    │   ├── Dockerfile
    │   └── app/
    │       ├── main.py            # Endpoint e routing
    │       ├── models.py          # Modelli SQLAlchemy
    │       ├── schemas.py         # Schemi Pydantic
    │       ├── auth.py            # Autenticazione via header
    │       ├── db.py              # Connessione database
    │       ├── queue.py           # Connessione coda RQ
    │       └── rules.py           # Regole di trading
    ├── worker/                    # RQ Worker
    │   ├── Dockerfile
    │   └── worker/
    │       ├── run.py             # Entry point worker
    │       ├── jobs.py            # Job di esecuzione trade
    │       ├── executors.py       # Connettori MT5/cTrader
    │       ├── models.py          # Modelli condivisi
    │       ├── db.py              # Connessione database
    │       └── rules.py           # Regole di trading
    └── telegram/                  # Telegram Ingest
        ├── Dockerfile
        └── telegram_ingest/
            ├── run.py             # Entry point listener
            ├── parser.py          # Parsing segnali
            ├── models.py          # Modelli condivisi
            └── db.py              # Connessione database
```

