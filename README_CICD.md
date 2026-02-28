# Dupli – CI/CD: Deploy automatico con GitHub Actions

Deploy automatico sul server ad ogni push su `main`.

---

## Panoramica

Il workflow `.github/workflows/deploy.yml`:

1. Carica la chiave SSH privata nell'**ssh-agent** (`webfactory/ssh-agent`)
2. Aggiunge l'host del server a `known_hosts` via `ssh-keyscan`
3. Si connette al server via SSH ed esegue:
   ```
   cd <DEPLOY_PATH>
   git fetch --all && git reset --hard origin/main
   docker compose pull
   docker compose up -d --remove-orphans
   ```

Il deploy e' serializzato (nessun deploy parallelo) e ha un timeout di 10 minuti.

---

## Secrets richiesti

Configura in **GitHub** > **Settings** > **Secrets and variables** > **Actions**:

| Secret | Descrizione | Esempio |
|--------|-------------|---------|
| `DEPLOY_HOST` | IP o hostname del server | `203.0.113.10` |
| `DEPLOY_USER` | Utente SSH | `deploy` |
| `DEPLOY_SSH_KEY` | Chiave privata SSH (intero contenuto del file, incluse righe BEGIN/END) | Vedi sotto |
| `DEPLOY_PATH` | Path assoluto del repo sul server | `/opt/dupli` |

---

## Generare la chiave SSH

```bash
# 1. Genera coppia di chiavi Ed25519
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/dupli_deploy -N ""

# 2. Copia la chiave PUBBLICA sul server
ssh-copy-id -i ~/.ssh/dupli_deploy.pub <DEPLOY_USER>@<DEPLOY_HOST>

# 3. Verifica accesso
ssh -i ~/.ssh/dupli_deploy <DEPLOY_USER>@<DEPLOY_HOST> "echo OK"

# 4. Copia la chiave PRIVATA nel secret DEPLOY_SSH_KEY su GitHub
cat ~/.ssh/dupli_deploy
# (copia tutto l'output, incluse le righe -----BEGIN/END OPENSSH PRIVATE KEY-----)
```

---

## Preparazione server (prima volta)

```bash
# Come DEPLOY_USER sul server
sudo mkdir -p /opt/dupli && sudo chown $(whoami):$(whoami) /opt/dupli
git clone https://github.com/massimotrovato-git/dupli.git /opt/dupli
cd /opt/dupli
cp .env.example .env   # edita con valori di produzione
docker compose up -d --build
```

L'utente `DEPLOY_USER` deve poter usare Docker senza sudo:

```bash
sudo usermod -aG docker <DEPLOY_USER>
# logout/login per applicare
```

---

## Test

### 1. Trigger manuale

```bash
# Fai un commit vuoto su main per attivare il workflow
git commit --allow-empty -m "chore: trigger deploy test"
git push origin main
```

Poi verifica su **GitHub > Actions** che il workflow "Deploy to production" sia verde.

### 2. Verifica sul server

```bash
ssh <DEPLOY_USER>@<DEPLOY_HOST> "cd /opt/dupli && docker compose ps"
```

Tutti i servizi devono risultare `Up (healthy)`.

### 3. Verifica che altri branch NON attivino il deploy

```bash
git checkout -b test/no-deploy
git commit --allow-empty -m "test: should not trigger deploy"
git push origin test/no-deploy
# -> Nessun workflow deve attivarsi su GitHub Actions
```

### 4. Simulazione locale (senza GitHub Actions)

```bash
ssh <DEPLOY_USER>@<DEPLOY_HOST> bash -s << 'EOF'
  set -euo pipefail
  cd /opt/dupli
  git fetch --all
  git reset --hard origin/main
  docker compose pull
  docker compose up -d --remove-orphans
  docker compose ps
EOF
```

---

## Sicurezza

- Usa una chiave SSH **dedicata** al deploy (non riutilizzare chiavi personali)
- `DEPLOY_USER` deve avere permessi minimi: solo Docker e accesso a `DEPLOY_PATH`
- Valuta `command=` in `authorized_keys` per limitare i comandi eseguibili
- Non committare mai la chiave privata nel repository
- Ruota la chiave SSH periodicamente
