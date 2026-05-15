#!/usr/bin/env bash
# scripts/setup_server.sh — first-time bootstrap for a fresh Hetzner Cloud VM
#
# Run this as root on a freshly provisioned Ubuntu 24.04 box. It's idempotent:
# rerunning is safe and only changes what's drifted. See DEPLOYMENT.md for
# the full runbook (DNS, secrets, smoke-test).
#
# Assumes:
#   * Ubuntu 24.04 LTS, fresh
#   * SSH key already installed for root
#   * The DNS A record for wavetest.waveimpact.de points at this box
#   * /etc/wavetest-app/litestream.env and /etc/wavetest-app/rclone.conf
#     have been created with the real Hetzner Object Storage credentials
#     (copy from deploy/litestream.env.example + deploy/rclone.conf.example)

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/vjmayr/waveTest-App.git}"
DEPLOY_DIR="/opt/wavetest-app"
APP_USER="wavetest"
LITESTREAM_VERSION="0.3.13"
RCLONE_VERSION="current"  # the upstream installer picks the latest stable

log() { echo "[setup_server] $*"; }

if [[ "${EUID}" -ne 0 ]]; then
    echo "Must run as root." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# 1. System packages + hardening
# ---------------------------------------------------------------------------
log "Updating apt index + installing base packages…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y \
    python3.12 python3.12-venv python3-pip \
    git curl ca-certificates \
    sqlite3 \
    ufw fail2ban unattended-upgrades \
    debian-keyring debian-archive-keyring apt-transport-https

# Caddy from the official repo (apt's caddy is too old).
if ! command -v caddy >/dev/null; then
    log "Installing Caddy from the official repo…"
    curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/gpg.key \
        | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt \
        > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -qq
    apt-get install -y caddy
fi

# Litestream — pinned version, single binary.
if ! command -v litestream >/dev/null; then
    log "Installing Litestream ${LITESTREAM_VERSION}…"
    curl -fsSL -o /tmp/litestream.deb \
        "https://github.com/benbjohnson/litestream/releases/download/v${LITESTREAM_VERSION}/litestream-v${LITESTREAM_VERSION}-linux-amd64.deb"
    dpkg -i /tmp/litestream.deb
    rm /tmp/litestream.deb
    # The .deb ships its own service unit and config; we disable both — we
    # ship our own from deploy/systemd/ so config lives in git.
    systemctl disable --now litestream || true
fi

# rclone — used to back up auth/users.yaml.
if ! command -v rclone >/dev/null; then
    log "Installing rclone…"
    curl -fsSL https://rclone.org/install.sh | bash
fi

# UFW: SSH + HTTP + HTTPS. HTTP is open so Caddy can serve the ACME challenge.
log "Configuring ufw…"
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow http
ufw allow https
ufw --force enable

# Unattended security upgrades — Ubuntu's default config covers main + security.
log "Enabling unattended-upgrades…"
dpkg-reconfigure -plow unattended-upgrades || true

# ---------------------------------------------------------------------------
# 2. App user + deploy directory
# ---------------------------------------------------------------------------
if ! id "${APP_USER}" >/dev/null 2>&1; then
    log "Creating ${APP_USER} system user…"
    useradd --system --create-home --shell /usr/sbin/nologin "${APP_USER}"
fi

mkdir -p "${DEPLOY_DIR}"
chown "${APP_USER}:${APP_USER}" "${DEPLOY_DIR}"

# ---------------------------------------------------------------------------
# 3. Clone / refresh the repo
# ---------------------------------------------------------------------------
if [[ ! -d "${DEPLOY_DIR}/.git" ]]; then
    log "Cloning ${REPO_URL} into ${DEPLOY_DIR}…"
    sudo -u "${APP_USER}" git clone "${REPO_URL}" "${DEPLOY_DIR}"
else
    log "Pulling latest from main…"
    sudo -u "${APP_USER}" git -C "${DEPLOY_DIR}" pull --ff-only origin main
fi

# Writable subdirs for SQLite + reports.
sudo -u "${APP_USER}" mkdir -p "${DEPLOY_DIR}/data" "${DEPLOY_DIR}/artifacts" "${DEPLOY_DIR}/auth"

# ---------------------------------------------------------------------------
# 4. Python venv + dependencies + Alembic migrations
# ---------------------------------------------------------------------------
if [[ ! -d "${DEPLOY_DIR}/.venv" ]]; then
    log "Creating Python venv…"
    sudo -u "${APP_USER}" python3.12 -m venv "${DEPLOY_DIR}/.venv"
fi

log "Installing app + pinned dependencies…"
sudo -u "${APP_USER}" "${DEPLOY_DIR}/.venv/bin/pip" install --upgrade pip wheel
sudo -u "${APP_USER}" "${DEPLOY_DIR}/.venv/bin/pip" install -e "${DEPLOY_DIR}"

# Toolchain packages — install_toolchain.sh expects a sibling checkout of
# RAI-TOOLCHAIN. The runbook covers cloning that separately; if it's already
# present at /opt/RAI-TOOLCHAIN we wire it up automatically.
if [[ -d /opt/RAI-TOOLCHAIN ]]; then
    log "Linking toolchain from /opt/RAI-TOOLCHAIN…"
    sudo -u "${APP_USER}" bash "${DEPLOY_DIR}/scripts/install_toolchain.sh" /opt/RAI-TOOLCHAIN
else
    log "⚠  /opt/RAI-TOOLCHAIN not found — toolchain packages will be missing."
    log "   See DEPLOYMENT.md §Toolchain checkout."
fi

log "Running Alembic migrations…"
sudo -u "${APP_USER}" bash -c "cd ${DEPLOY_DIR} && .venv/bin/alembic upgrade head"

# ---------------------------------------------------------------------------
# 5. Install systemd units + Caddyfile
# ---------------------------------------------------------------------------
log "Installing systemd units…"
install -m 0644 "${DEPLOY_DIR}/deploy/systemd/wavetest-app.service"          /etc/systemd/system/
install -m 0644 "${DEPLOY_DIR}/deploy/systemd/litestream.service"            /etc/systemd/system/
install -m 0644 "${DEPLOY_DIR}/deploy/systemd/wavetest-auth-backup.service"  /etc/systemd/system/
install -m 0644 "${DEPLOY_DIR}/deploy/systemd/wavetest-auth-backup.timer"    /etc/systemd/system/

log "Installing Caddyfile…"
install -m 0644 "${DEPLOY_DIR}/deploy/Caddyfile" /etc/caddy/Caddyfile

log "Installing Litestream config…"
mkdir -p /etc/wavetest-app
install -m 0644 "${DEPLOY_DIR}/deploy/litestream.yml" /etc/wavetest-app/litestream.yml
chown root:"${APP_USER}" /etc/wavetest-app/litestream.yml
chmod 0640 /etc/wavetest-app/litestream.yml

# litestream.env and rclone.conf must exist (operator copies them from the
# .example files before running this script). Fail fast if they don't.
for f in /etc/wavetest-app/litestream.env /etc/wavetest-app/rclone.conf; do
    if [[ ! -f "$f" ]]; then
        log "❌ Missing ${f}. Copy from deploy/$(basename "$f" .env).env.example"
        log "   (or deploy/rclone.conf.example) and fill in credentials."
        exit 1
    fi
    chown root:"${APP_USER}" "$f"
    chmod 0640 "$f"
done

systemctl daemon-reload
systemctl enable --now caddy
systemctl enable --now litestream
systemctl enable --now wavetest-app
systemctl enable --now wavetest-auth-backup.timer

log "✅ Setup complete."
log ""
log "Next steps (see DEPLOYMENT.md):"
log "  1. Bootstrap the first admin user:"
log "       sudo -u ${APP_USER} ${DEPLOY_DIR}/.venv/bin/python \\"
log "         ${DEPLOY_DIR}/scripts/auth_add_user.py --role admin"
log "  2. Visit https://wavetest.waveimpact.de — Caddy will issue the cert"
log "     on the first request (takes 5–30 seconds)."
log "  3. Verify Litestream:  sudo -u ${APP_USER} litestream snapshots \\"
log "         -config /etc/wavetest-app/litestream.yml \\"
log "         ${DEPLOY_DIR}/data/wavetest_app.db"
