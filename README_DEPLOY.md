# Dupli – Deployment & Operations Runbook

Guida completa per il deploy e l'operativita' della piattaforma Dupli Copy-Trading.

---

## Indice

1. [Prerequisiti](#prerequisiti)
2. [Architettura](#architettura)
3. [Variabili d'ambiente (.env)](#variabili-dambiente)
4. [Avvio locale (step-by-step)](#avvio-locale-step-by-step)
5. [Inizializzazione Keycloak](#inizializzazione-keycloak)
6. [Accesso all'applicazione](#accesso-allapplicazione)
7. [Deploy in produzione](#deploy-in-produzione)
8. [Comandi utili](#comandi-utili)
9. [Troubleshooting](#troubleshooting)
10. [Sicurezza](#sicurezza)

---

## Prerequisiti

| Requisito | Versione minima | Note |
|-----------|----------------|------|
| Docker | >= 24.0 | [Installazione](https://docs.docker.com/get-docker/) |
| Docker Compose | >= 2.20 | Incluso con Docker Desktop |
| `openssl` | qualsiasi | Per certificati self-signed (solo dev locale) |
| `curl` | qualsiasi | Per lo script di setup Keycloak |
| `python3` | >= 3.8 | Per lo script di setup Keycloak |
| Git | qualsiasi | |

---

## Architettura

```
                  +-----------+
  Browser ------->|   Nginx   | :80/443
                  +-----+-----+
                        |
                  +-----v--------+       +---------------+
                  | oauth2-proxy |<----->|   Keycloak     | :8081
                  +-----+--------+       | (OIDC / TOTP)  |
                        |                +---------------+
                  +-----v-----+    +-------+    +-----------+
                  |  FastAPI   |<-->| Redis |<-->|  Worker   |
                  |   (API)    |    +-------+    | (RQ exec) |
                  +-----+------+                +-----------+
                        |
                  +-----v------+    +------------+
                  | PostgreSQL |    |  Telegram   |
                  +------------+    | (ingest)    |
                                    +------------+
```

### Servizi

| Servizio | Immagine / Build | Porta esposta | Healthcheck |
|----------|-----------------|---------------|-------------|
| **postgres** | `postgres:16` | - | `pg_isready` |
| **redis** | `redis:7` | - | `redis-cli ping` |
| **keycloak** | `quay.io/keycloak/keycloak:25.0` | `8081:8080` | TCP probe :8080 |
| **oauth2-proxy** | `./infra/oauth2-proxy` (build) | - | `curl /ping` |
| **api** | `./services/api` (build) | - | HTTP GET `/api/health` |
| **worker** | `./services/worker` (build) | - | - |
| **telegram** | `./services/telegram` (build) | - | - |
| **nginx** | `nginx:1.27` | `80, 443` | `curl -fsk` |

Tutti i servizi hanno `restart: unless-stopped` e dipendenze con `condition: service_healthy` dove applicabile.

---

## Variabili d'ambiente

Copia il template e personalizza:

```bash
cp .env.example .env
```

### Variabili principali

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `APP_ENV` | `dev` | `dev` o `prod` |
| `APP_BASE_URL` | `https://localhost` | URL pubblico dell'app |
| `APP_SECRET_KEY` | - | Stringa random per session signing |
| `POSTGRES_DB` | `dupli` | Nome database |
| `POSTGRES_USER` | `dupli` | Utente database |
| `POSTGRES_PASSWORD` | - | **Obbligatorio**: password database |
| `REDIS_URL` | `redis://redis:6379/0` | URL connessione Redis |
| `REDIS_PASSWORD` | (vuoto) | Password Redis (opzionale) |
| `KEYCLOAK_ADMIN` | `admin` | Username admin Keycloak |
| `KEYCLOAK_ADMIN_PASSWORD` | - | **Obbligatorio**: password admin Keycloak |
| `KEYCLOAK_URL` | `http://keycloak:8080` | URL interno (non cambiare) |
| `KEYCLOAK_HOST_PORT` | `8081` | Porta host per admin console |
| `OAUTH2_PROXY_CLIENT_ID` | `oauth2-proxy` | Client ID in Keycloak |
| `OAUTH2_PROXY_CLIENT_SECRET` | - | **Obbligatorio**: deve corrispondere al secret nel realm |
| `OAUTH2_PROXY_COOKIE_SECRET` | - | **Obbligatorio**: 32 byte base64 |
| `OAUTH2_PROXY_REDIRECT_URL` | `https://localhost/oauth2/callback` | Deve corrispondere al redirect URI in Keycloak |
| `OAUTH2_PROXY_COOKIE_SECURE` | `true` | `false` per dev locale con self-signed certs |
| `TELEGRAM_API_ID` | - | Da https://my.telegram.org |
| `TELEGRAM_API_HASH` | - | Da https://my.telegram.org |
| `TELEGRAM_SESSION_STRING` | - | **Obbligatorio**: Telethon StringSession (vedi sotto) |
| `MT5_GATEWAY_URL` | `http://mt5-gateway:8090` | URL del gateway MT5 (Windows) |
| `MT5_ENABLED` | `true` | Abilita executor MT5 |
| `CTRADER_ENABLED` | `false` | Abilita executor cTrader |

### Generare i secret

```bash
# APP_SECRET_KEY e OAUTH2_PROXY_COOKIE_SECRET
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# OAUTH2_PROXY_CLIENT_SECRET: deve corrispondere a quello in realm-export.json
# Aggiorna entrambi i file contemporaneamente
```

---

## Avvio locale (step-by-step)

### 1. Clona il repository

```bash
git clone https://github.com/massimotrovato-git/dupli.git
cd dupli
```

### 2. Configura l'ambiente

```bash
cp .env.example .env
# Edita .env con i tuoi valori (vedi tabella sopra)
```

Per sviluppo locale, modifica almeno:
- `OAUTH2_PROXY_COOKIE_SECURE=false`
- `POSTGRES_PASSWORD=<una password>`
- `KEYCLOAK_ADMIN_PASSWORD=<una password>`
- `APP_SECRET_KEY=<stringa random>`
- `OAUTH2_PROXY_COOKIE_SECRET=<stringa random>`
- `OAUTH2_PROXY_CLIENT_SECRET=<deve corrispondere a realm-export.json>`

### 3. Genera certificati TLS self-signed

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout infra/nginx/certs/privkey.pem \
  -out infra/nginx/certs/fullchain.pem \
  -subj "/CN=localhost"
```

> Il browser mostrera' un avviso di certificato non attendibile. Accetta l'eccezione.

### 4. Aggiorna il realm Keycloak (opzionale)

Se hai cambiato `OAUTH2_PROXY_CLIENT_SECRET` o il dominio, aggiorna `infra/keycloak/realm-export.json`:
- Campo `secret` nel client `oauth2-proxy`
- Campo `redirectUris` con il tuo dominio

### 5. Avvia lo stack

```bash
docker compose up -d --build
```

La prima build scarica le immagini e installa le dipendenze Python (~2-5 min).

### 6. Verifica lo stato

```bash
docker compose ps
```

Tutti i servizi devono risultare `Up (healthy)`. Se un servizio non parte, consulta i log:

```bash
docker compose logs -f <nome-servizio>
```

### 7. Inizializza Keycloak (post-avvio)

Vedi la sezione successiva.

---

## Inizializzazione Keycloak

### Opzione A: Realm import automatico (default)

Il `docker-compose.yml` monta `infra/keycloak/realm-export.json` e lo importa all'avvio di Keycloak con il flag `--import-realm`. Questo crea automaticamente:
- Realm `dupli`
- Ruoli: `admin`, `operator`, `viewer`
- Gruppi: `admins`, `operators`, `viewers` (con mapping ai ruoli)
- Client scope `dupli-roles` con i mapper per roles, groups, preferred_username
- Client `oauth2-proxy` (confidential)
- Client `dupli-api` (service account)

### Opzione B: Script idempotente (post-import)

Per setup aggiuntivo (utenti, aggiornamento redirect URI), usa lo script:

```bash
# Dalla macchina host (Keycloak deve essere in esecuzione)
KEYCLOAK_BASE=http://localhost:8081 \
KEYCLOAK_ADMIN=admin \
KEYCLOAK_ADMIN_PASSWORD=<tua-password> \
REALM=dupli \
APP_DOMAIN=https://localhost \
BOOTSTRAP_USER=admin1 \
BOOTSTRAP_PASSWORD=<password-admin1> \
BOOTSTRAP_EMAIL=admin@example.com \
  bash infra/keycloak/setup-keycloak.sh
```

Lo script e' **idempotente**: puo' essere eseguito piu' volte senza effetti collaterali. Effettua:
1. Verifica/crea i ruoli realm (`admin`, `operator`, `viewer`)
2. Verifica/crea i gruppi (`admins`, `operators`, `viewers`) con mapping ai ruoli
3. Aggiorna il redirect URI del client `oauth2-proxy` (se `APP_DOMAIN` e' specificato)
4. Crea un utente bootstrap con ruolo `admin` e TOTP richiesto (se `BOOTSTRAP_USER` e' specificato)

### Opzione C: Setup manuale via Admin Console

1. Apri **http://localhost:8081** (o la porta configurata in `KEYCLOAK_HOST_PORT`)
2. Accedi con `KEYCLOAK_ADMIN` / `KEYCLOAK_ADMIN_PASSWORD`
3. Seleziona il realm **dupli**
4. **Users** -> **Add user**:
   - Compila username, email
   - Tab **Credentials**: imposta password (disabilita "Temporary")
   - Tab **Role mapping**: assegna `admin`, `operator`, o `viewer`
   - Tab **Required Actions**: aggiungi `Configure OTP` per abilitare MFA

---

## Accesso all'applicazione

| URL | Descrizione |
|-----|-------------|
| `https://localhost` | App principale (Nginx -> oauth2-proxy -> FastAPI) |
| `https://localhost/docs` | Swagger UI (API interattiva) |
| `https://localhost/ui` | UI web minimale |
| `http://localhost:8081` | Console admin Keycloak |

Al primo accesso, sarai rediretto a Keycloak per il login. Se l'utente ha TOTP richiesto, dovra' configurare l'authenticator al primo login.

---

## Deploy in produzione

### Checklist pre-deploy

- [ ] Certificati TLS reali (Let's Encrypt o altro CA) in `infra/nginx/certs/`
- [ ] `.env` con valori di produzione:
  - `APP_ENV=prod`
  - `APP_BASE_URL=https://tuo-dominio.com`
  - `OAUTH2_PROXY_REDIRECT_URL=https://tuo-dominio.com/oauth2/callback`
  - `OAUTH2_PROXY_COOKIE_SECURE=true`
  - Password forti per Postgres, Keycloak, e tutti i secret
- [ ] `infra/keycloak/realm-export.json` aggiornato:
  - `redirectUris` e `webOrigins` con il dominio corretto
  - `secret` del client aggiornato
- [ ] Firewall configurato:
  - Porta 80/443: aperte (Nginx)
  - Porta 8081 (Keycloak admin): solo localhost o IP trusted
  - Porta MT5 gateway: solo dall'IP del server CORE
- [ ] Backup strategy per `pgdata` volume

### Avvio produzione

```bash
# Prima volta
docker compose up -d --build

# Setup Keycloak
APP_DOMAIN=https://tuo-dominio.com \
KEYCLOAK_BASE=http://localhost:8081 \
KEYCLOAK_ADMIN=admin \
KEYCLOAK_ADMIN_PASSWORD=<password> \
BOOTSTRAP_USER=admin1 \
BOOTSTRAP_PASSWORD=<password> \
BOOTSTRAP_EMAIL=admin@tuo-dominio.com \
  bash infra/keycloak/setup-keycloak.sh
```

### Aggiornamenti

```bash
git pull
docker compose up -d --build
```

---

## Comandi utili

```bash
# Avvia in foreground (log in tempo reale)
docker compose up --build

# Ferma tutti i servizi
docker compose down

# Ferma e rimuovi volumi (ATTENZIONE: cancella tutti i dati!)
docker compose down -v

# Ricostruisci un singolo servizio
docker compose up -d --build api

# Visualizza log di un servizio
docker compose logs -f api
docker compose logs -f keycloak
docker compose logs -f worker

# Accedi alla shell di un container
docker compose exec api bash
docker compose exec postgres psql -U dupli -d dupli

# Verifica healthcheck di tutti i servizi
docker compose ps

# Restart di un singolo servizio
docker compose restart worker
```

---

## Troubleshooting

### Keycloak non raggiunge lo stato "healthy"

```bash
docker compose logs keycloak
# Verifica che KC_DB, KEYCLOAK_ADMIN, KEYCLOAK_ADMIN_PASSWORD siano corretti
# Keycloak impiega ~30-60s per avviarsi la prima volta
```

### oauth2-proxy non si avvia / errore OIDC

```bash
docker compose logs oauth2-proxy
# Cause comuni:
# - OAUTH2_PROXY_CLIENT_SECRET non corrisponde al secret in realm-export.json
# - KEYCLOAK_URL non raggiungibile dall'interno del container
# - Realm "dupli" non importato correttamente
```

### Nginx restituisce 502 Bad Gateway

```bash
docker compose logs nginx
docker compose logs oauth2-proxy
# oauth2-proxy potrebbe non essere ancora pronto
# Verifica: docker compose ps (tutti i servizi devono essere healthy)
```

### API non risponde

```bash
docker compose logs api
# Verifica connessione a Postgres:
docker compose exec api python -c "from app.db import engine; print(engine.url)"
```

### Worker non esegue i job

```bash
docker compose logs worker
# Verifica connessione a Redis:
docker compose exec worker python -c "import redis,os; r=redis.from_url(os.getenv('REDIS_URL')); print(r.ping())"
```

### Telegram ingest non funziona

```bash
docker compose logs telegram
# Verifica:
# - TELEGRAM_API_ID e TELEGRAM_API_HASH validi
# - TELEGRAM_SESSION_STRING: deve essere una StringSession valida (vedi sotto)
# - TELEGRAM_SOURCE_CHAT_ID: deve essere l'ID numerico del canale/gruppo
```

### Generare la TELEGRAM_SESSION_STRING

La session string va generata **una volta** sulla tua macchina locale (non nel container).
Richiede l'accesso interattivo per inserire il codice di verifica Telegram.

```bash
pip install telethon
python3 -c "
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = int(input('TELEGRAM_API_ID: '))
api_hash = input('TELEGRAM_API_HASH: ')

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print()
    print('=== TELEGRAM_SESSION_STRING ===')
    print(client.session.save())
    print('================================')
"
```

1. Inserisci `api_id` e `api_hash` (da https://my.telegram.org)
2. Inserisci il numero di telefono e il codice di verifica
3. Copia la stringa stampata e incollala in `.env` come `TELEGRAM_SESSION_STRING`

> **Nota**: la session string non scade finche' non fai logout o revochi la sessione da Telegram.

---

## Sicurezza

Per i dettagli completi sulla politica RBAC, ruoli, scopes e claims, vedi:
- [`infra/security/RBAC_POLICY.md`](infra/security/RBAC_POLICY.md)

### Punti chiave

- oauth2-proxy accetta solo richieste inoltrate da Nginx
- Non esporre la porta 8081 (Keycloak admin) su internet
- Non committare il file `.env` nel repository
- In produzione: `OAUTH2_PROXY_COOKIE_SECURE=true` sempre
- Abilitare TOTP/MFA per tutti gli utenti
- Brute-force protection attiva nel realm Keycloak
- Token di accesso con lifetime di 5 minuti
- Ruotare periodicamente tutti i secret

---

## MT5 Gateway (Windows)

Il gateway MT5 va eseguito su una macchina Windows con MT5 installato.
Vedi [`windows/mt5-gateway/README.md`](windows/mt5-gateway/README.md).

Il server Linux comunica con esso tramite `MT5_GATEWAY_URL`.

Configura il firewall Windows per accettare connessioni solo dall'IP del server CORE.
