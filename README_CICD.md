# Dupli – CI/CD con GitHub Actions

Guida per configurare il deploy automatico via GitHub Actions.

---

## Come funziona

Ogni **push su `main`** attiva il workflow `.github/workflows/deploy.yml` che:

1. Si connette al server via SSH
2. Esegue `git fetch --all && git reset --hard origin/main`
3. Esegue `docker compose pull` per aggiornare le immagini
4. Esegue `docker compose up -d --remove-orphans` per riavviare i servizi

Il workflow usa [appleboy/ssh-action](https://github.com/appleboy/ssh-action) e ha `concurrency` configurata per evitare deploy paralleli.

---

## Prerequisiti

- Server Linux con Docker e Docker Compose installati
- Repository clonato sul server nel path di deploy
- File `.env` configurato sul server (vedi [README_DEPLOY.md](README_DEPLOY.md))
- Certificati TLS in `infra/nginx/certs/` sul server

---

## 1. Generare la chiave SSH per GitHub Actions

Sul tuo computer locale (o sul server):

```bash
# Genera una coppia di chiavi Ed25519 (piu' sicura di RSA)
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/dupli_deploy -N ""
```

Questo crea due file:
- `~/.ssh/dupli_deploy` – chiave **privata** (da inserire nei GitHub Secrets)
- `~/.ssh/dupli_deploy.pub` – chiave **pubblica** (da aggiungere al server)

### Aggiungere la chiave pubblica al server

```bash
# Copia la chiave pubblica sul server
ssh-copy-id -i ~/.ssh/dupli_deploy.pub <DEPLOY_USER>@<DEPLOY_HOST>

# Oppure manualmente:
cat ~/.ssh/dupli_deploy.pub | ssh <DEPLOY_USER>@<DEPLOY_HOST> "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

### Verificare l'accesso

```bash
ssh -i ~/.ssh/dupli_deploy <DEPLOY_USER>@<DEPLOY_HOST> "echo OK"
```

---

## 2. Configurare i GitHub Secrets

Vai su **GitHub** > repo `dupli` > **Settings** > **Secrets and variables** > **Actions** > **New repository secret**.

Aggiungi i seguenti secret:

| Secret | Descrizione | Esempio |
|--------|-------------|---------|
| `DEPLOY_HOST` | IP o hostname del server | `203.0.113.10` |
| `DEPLOY_USER` | Utente SSH sul server | `deploy` |
| `DEPLOY_SSH_KEY` | Contenuto della chiave **privata** | `cat ~/.ssh/dupli_deploy` (tutto il contenuto, incluse le righe BEGIN/END) |
| `DEPLOY_PATH` | Path assoluto del repository sul server | `/opt/dupli` |

> **IMPORTANTE**: per `DEPLOY_SSH_KEY`, copia l'intero contenuto del file della chiave privata, incluse le righe `-----BEGIN OPENSSH PRIVATE KEY-----` e `-----END OPENSSH PRIVATE KEY-----`.

---

## 3. Preparare il server

### Prima volta

```bash
# Sul server, come DEPLOY_USER
sudo mkdir -p /opt/dupli
sudo chown $(whoami):$(whoami) /opt/dupli

# Clona il repository
git clone https://github.com/massimotrovato-git/dupli.git /opt/dupli
cd /opt/dupli

# Configura l'ambiente
cp .env.example .env
# Edita .env con i valori di produzione (vedi README_DEPLOY.md)

# Genera certificati TLS (o copia quelli reali)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout infra/nginx/certs/privkey.pem \
  -out infra/nginx/certs/fullchain.pem \
  -subj "/CN=tuo-dominio.com"

# Primo avvio
docker compose up -d --build

# Inizializza Keycloak (vedi README_DEPLOY.md per i dettagli)
bash infra/keycloak/setup-keycloak.sh
```

### Permessi Docker

L'utente `DEPLOY_USER` deve poter eseguire Docker senza `sudo`:

```bash
sudo usermod -aG docker <DEPLOY_USER>
# Effettua logout/login per applicare
```

---

## 4. Test rapido

### Verifica manuale del workflow

1. Fai una modifica qualsiasi su `main` (es. aggiorna un commento in un file)
2. Pusha su `main`:
   ```bash
   git add -A && git commit -m "test: trigger deploy" && git push origin main
   ```
3. Vai su **GitHub** > **Actions** > verifica che il workflow "Deploy to Server" si avvii
4. Controlla i log del workflow per confermare che il deploy sia andato a buon fine
5. Verifica sul server:
   ```bash
   ssh <DEPLOY_USER>@<DEPLOY_HOST> "cd /opt/dupli && docker compose ps"
   ```

### Verifica che il workflow non si attivi su branch diversi da main

1. Crea un branch:
   ```bash
   git checkout -b test/no-deploy
   git commit --allow-empty -m "test: should not trigger deploy"
   git push origin test/no-deploy
   ```
2. Verifica su **GitHub** > **Actions** che **nessun** workflow si sia avviato

### Simulare il deploy in locale

Per testare i comandi senza GitHub Actions:

```bash
ssh <DEPLOY_USER>@<DEPLOY_HOST> << 'EOF'
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

- La chiave SSH deve essere **dedicata** al deploy (non riutilizzare chiavi personali)
- L'utente `DEPLOY_USER` dovrebbe avere permessi minimi (solo Docker e accesso al path di deploy)
- Considera l'uso di `command=` in `authorized_keys` per limitare i comandi eseguibili
- Non committare mai la chiave privata nel repository
- Ruota periodicamente la chiave SSH
