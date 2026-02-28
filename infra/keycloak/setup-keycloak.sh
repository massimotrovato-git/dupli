#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# Dupli – Idempotent Keycloak post-import setup script
# ─────────────────────────────────────────────────────────────────
# This script runs AFTER Keycloak has imported the realm via
# realm-export.json.  It uses the Admin REST API to:
#   1. Ensure realm roles exist (admin, operator, viewer)
#   2. Ensure groups exist and have the correct role mappings
#   3. Ensure the oauth2-proxy client has the right redirect URIs
#   4. Optionally create a bootstrap admin user
#
# Usage:
#   ./setup-keycloak.sh              # uses env vars or defaults
#   KEYCLOAK_BASE=http://keycloak:8080 \
#   KEYCLOAK_ADMIN=admin \
#   KEYCLOAK_ADMIN_PASSWORD=changeme \
#   REALM=dupli \
#   BOOTSTRAP_USER=admin1 \
#   BOOTSTRAP_PASSWORD=changeme \
#   BOOTSTRAP_EMAIL=admin@example.com \
#   APP_DOMAIN=https://copytrading.example.com \
#     ./setup-keycloak.sh
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

KC_BASE="${KEYCLOAK_BASE:-http://localhost:8081}"
KC_ADMIN="${KEYCLOAK_ADMIN:-admin}"
KC_ADMIN_PWD="${KEYCLOAK_ADMIN_PASSWORD:-admin_change_me}"
REALM="${REALM:-dupli}"
APP_DOMAIN="${APP_DOMAIN:-}"
BOOTSTRAP_USER="${BOOTSTRAP_USER:-}"
BOOTSTRAP_PASSWORD="${BOOTSTRAP_PASSWORD:-}"
BOOTSTRAP_EMAIL="${BOOTSTRAP_EMAIL:-}"

# ── helpers ───────────────────────────────────────────────────────
log()  { printf '\033[1;34m[keycloak-setup]\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m[keycloak-setup]\033[0m %s\n' "$*" >&2; }
die()  { err "$@"; exit 1; }

get_token() {
  local resp
  resp=$(curl -sf -X POST "${KC_BASE}/realms/master/protocol/openid-connect/token" \
    -d "client_id=admin-cli" \
    -d "username=${KC_ADMIN}" \
    -d "password=${KC_ADMIN_PWD}" \
    -d "grant_type=password") || die "Cannot authenticate to Keycloak at ${KC_BASE}"
  echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])"
}

kc_get()  { curl -sf -H "Authorization: Bearer ${TOKEN}" "${KC_BASE}/admin/realms/${REALM}$1"; }
kc_post() { curl -sf -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" -X POST "${KC_BASE}/admin/realms/${REALM}$1" -d "$2"; }
kc_put()  { curl -sf -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" -X PUT  "${KC_BASE}/admin/realms/${REALM}$1" -d "$2"; }

# ── wait for Keycloak ─────────────────────────────────────────────
log "Waiting for Keycloak at ${KC_BASE} ..."
for i in $(seq 1 30); do
  curl -sf "${KC_BASE}/realms/master" > /dev/null 2>&1 && break
  sleep 2
done
curl -sf "${KC_BASE}/realms/master" > /dev/null 2>&1 || die "Keycloak not reachable after 60s"
log "Keycloak is up."

TOKEN=$(get_token)
log "Authenticated as ${KC_ADMIN}."

# ── 1. Ensure realm roles ────────────────────────────────────────
ensure_role() {
  local role_name="$1" role_desc="$2"
  local existing
  existing=$(kc_get "/roles/${role_name}" 2>/dev/null || true)
  if [ -z "$existing" ]; then
    log "Creating realm role: ${role_name}"
    kc_post "/roles" "{\"name\":\"${role_name}\",\"description\":\"${role_desc}\"}" > /dev/null
  else
    log "Role '${role_name}' already exists – OK"
  fi
}

ensure_role "admin"    "Full platform administration"
ensure_role "operator" "Operational access – CRUD + execution"
ensure_role "viewer"   "Read-only access"

# ── 2. Ensure groups ─────────────────────────────────────────────
ensure_group() {
  local group_name="$1" role_name="$2"
  local groups_json group_id role_json role_id

  groups_json=$(kc_get "/groups?search=${group_name}&exact=true" 2>/dev/null || echo "[]")
  group_id=$(echo "$groups_json" | python3 -c "
import sys, json
gs = json.load(sys.stdin)
for g in gs:
    if g['name'] == '${group_name}':
        print(g['id']); break
" 2>/dev/null || true)

  if [ -z "$group_id" ]; then
    log "Creating group: ${group_name}"
    kc_post "/groups" "{\"name\":\"${group_name}\"}" > /dev/null
    groups_json=$(kc_get "/groups?search=${group_name}&exact=true")
    group_id=$(echo "$groups_json" | python3 -c "
import sys, json
gs = json.load(sys.stdin)
for g in gs:
    if g['name'] == '${group_name}':
        print(g['id']); break
")
  else
    log "Group '${group_name}' already exists – OK"
  fi

  # Map role to group
  role_json=$(kc_get "/roles/${role_name}")
  role_id=$(echo "$role_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
  kc_post "/groups/${group_id}/role-mappings/realm" "[{\"id\":\"${role_id}\",\"name\":\"${role_name}\"}]" > /dev/null 2>&1 || true
  log "Group '${group_name}' -> role '${role_name}' mapped."
}

ensure_group "admins"    "admin"
ensure_group "operators" "operator"
ensure_group "viewers"   "viewer"

# ── 3. Update oauth2-proxy client redirect URI ───────────────────
if [ -n "$APP_DOMAIN" ]; then
  log "Updating oauth2-proxy redirect URI to ${APP_DOMAIN}/oauth2/callback ..."
  clients_json=$(kc_get "/clients?clientId=oauth2-proxy")
  client_id=$(echo "$clients_json" | python3 -c "import sys,json; cs=json.load(sys.stdin); print(cs[0]['id'] if cs else '')")
  if [ -n "$client_id" ]; then
    kc_put "/clients/${client_id}" "{\"redirectUris\":[\"${APP_DOMAIN}/oauth2/callback\"],\"webOrigins\":[\"${APP_DOMAIN}\"]}" > /dev/null
    log "oauth2-proxy client updated."
  else
    err "oauth2-proxy client not found in realm '${REALM}'"
  fi
fi

# ── 4. Bootstrap admin user (optional) ───────────────────────────
if [ -n "$BOOTSTRAP_USER" ] && [ -n "$BOOTSTRAP_PASSWORD" ]; then
  log "Checking bootstrap user '${BOOTSTRAP_USER}' ..."
  existing_users=$(kc_get "/users?username=${BOOTSTRAP_USER}&exact=true" 2>/dev/null || echo "[]")
  user_count=$(echo "$existing_users" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")

  if [ "$user_count" = "0" ]; then
    log "Creating bootstrap user '${BOOTSTRAP_USER}' ..."
    user_payload=$(python3 -c "
import json
print(json.dumps({
    'username': '${BOOTSTRAP_USER}',
    'email': '${BOOTSTRAP_EMAIL}' or '${BOOTSTRAP_USER}@localhost',
    'enabled': True,
    'emailVerified': True,
    'credentials': [{'type': 'password', 'value': '${BOOTSTRAP_PASSWORD}', 'temporary': False}],
    'requiredActions': ['CONFIGURE_TOTP']
}))
")
    kc_post "/users" "$user_payload" > /dev/null

    # Assign admin role
    user_json=$(kc_get "/users?username=${BOOTSTRAP_USER}&exact=true")
    user_id=$(echo "$user_json" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
    role_json=$(kc_get "/roles/admin")
    role_id=$(echo "$role_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
    kc_post "/users/${user_id}/role-mappings/realm" "[{\"id\":\"${role_id}\",\"name\":\"admin\"}]" > /dev/null
    log "User '${BOOTSTRAP_USER}' created with admin role + TOTP required."
  else
    log "User '${BOOTSTRAP_USER}' already exists – skipping."
  fi
fi

log "Keycloak setup complete."
