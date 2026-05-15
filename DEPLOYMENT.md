# wavetest-app — Hetzner deployment runbook

This document is the operational counterpart to [README.md](README.md). It
covers everything specific to the **production** install at
`wavetest.waveimpact.de` — provisioning a fresh VM, deploying code updates,
managing users, and recovering from disaster.

The deployment is a single Hetzner Cloud VM running:

| Component | Role |
| --- | --- |
| Caddy | Reverse proxy, automatic Let's Encrypt TLS, HTTP→HTTPS redirect |
| Streamlit (`wavetest-app.service`) | The app — bound to `127.0.0.1:8501` |
| Litestream (`litestream.service`) | Streams the SQLite WAL to Hetzner Object Storage every second |
| `wavetest-auth-backup.timer` | Daily upload of `auth/users.yaml` to the same bucket |
| SQLite (`data/wavetest_app.db`) | All persistent state — clients, projects, audit log, etc. |

All config lives in [deploy/](deploy/); secrets live in `/etc/wavetest-app/`
on the box and are not in git.

---

## 1. One-time provisioning

### 1.1. Create the VM

In the Hetzner Cloud Console:

- **Location**: Falkenstein (`fsn1`) — keeps customer data inside Germany.
- **Image**: Ubuntu 24.04 LTS.
- **Type**: `CPX21` (3 vCPU, 4 GB RAM, 80 GB SSD) is the recommended starting
  size. `CPX31` if heavy CV/NLP modules will run there often.
- **SSH key**: upload your public key — root password auth stays disabled.
- **Networking**: IPv4 + IPv6 both fine. No load balancer needed.
- **Backups**: enable Hetzner's automatic backups (€1.20/mo for the CPX21) as
  a second line of defense alongside Litestream.

Note the VM's public IPv4 address.

### 1.2. DNS

Point `wavetest.waveimpact.de` at the VM's IPv4 (and optionally IPv6):

```
wavetest.waveimpact.de.  A     <ipv4>
wavetest.waveimpact.de.  AAAA  <ipv6>     # optional
```

Wait for propagation (`dig +short wavetest.waveimpact.de`) before running the
setup script — Caddy needs working DNS to issue the Let's Encrypt cert.

### 1.3. Object Storage bucket + credentials

In the Hetzner Console under **Object Storage**:

1. Create a bucket named `wavetest-app-backups` in the **Falkenstein** region.
2. Under **Manage Tokens**, create an access key + secret with read/write
   permission on this bucket. Save them — Hetzner shows the secret once.
3. Set a lifecycle rule on the `auth/` prefix to delete objects older than
   90 days (the daily `users.yaml` backup creates one timestamped object per
   day, which would grow unbounded otherwise). Litestream manages its own
   retention via the 720h (30-day) setting in [litestream.yml](deploy/litestream.yml).

### 1.4. Toolchain checkout (manual)

The six `wavetest_*` packages aren't on PyPI — they're installed editable
from a sibling checkout. SSH in as root and clone:

```bash
git clone <toolchain-repo-url> /opt/RAI-TOOLCHAIN
```

The setup script detects `/opt/RAI-TOOLCHAIN` and wires it up automatically.

### 1.5. Secrets

SSH in as root and create `/etc/wavetest-app/` with the two secret files:

```bash
mkdir -p /etc/wavetest-app
cd /opt/wavetest-app  # cloned by setup_server.sh, or clone manually first

# Litestream — Hetzner S3 credentials
cp deploy/litestream.env.example /etc/wavetest-app/litestream.env
$EDITOR /etc/wavetest-app/litestream.env   # fill in access key + secret

# rclone — same credentials, different config format
cp deploy/rclone.conf.example /etc/wavetest-app/rclone.conf
$EDITOR /etc/wavetest-app/rclone.conf
```

The setup script will fail with a clear error message if either file is
missing.

### 1.6. Run the setup script

```bash
cd /opt/wavetest-app  # if not already cloned, the script will clone it
bash scripts/setup_server.sh
```

This installs system packages, creates the `wavetest` user, sets up the
venv, runs migrations, drops the systemd units into place, and starts
everything. Idempotent — safe to re-run.

### 1.7. Bootstrap the first admin user

```bash
sudo -u wavetest /opt/wavetest-app/.venv/bin/python \
    /opt/wavetest-app/scripts/auth_add_user.py --role admin
```

Choose a strong password — this account creates all the others. The script
also generates a random JWT cookie key on first run; don't lose
`auth/users.yaml` (it's in the daily backup, see §3).

### 1.8. Smoke test

Visit `https://wavetest.waveimpact.de` in a browser. First request takes
5–30 seconds while Caddy negotiates the TLS cert; subsequent ones are fast.

Then verify the backup pipeline:

```bash
# Litestream — should show one or more recent snapshots
sudo -u wavetest litestream snapshots \
    -config /etc/wavetest-app/litestream.yml \
    /opt/wavetest-app/data/wavetest_app.db

# Manually trigger the auth backup once to confirm it works
sudo systemctl start wavetest-auth-backup.service
sudo -u wavetest rclone --config /etc/wavetest-app/rclone.conf \
    ls hetzner:wavetest-app-backups/auth/
```

You should see at least one `users.<timestamp>.yaml` listed.

---

## 2. Deploying updates

For day-to-day code changes, on the VM:

```bash
sudo -u wavetest bash -c '
    cd /opt/wavetest-app
    git pull --ff-only origin main
    .venv/bin/pip install -e .       # only needed if pyproject.toml changed
    .venv/bin/alembic upgrade head   # only if new migrations
'
sudo systemctl restart wavetest-app
```

If only Python code changed (no deps, no migrations), the restart on its own
is enough — `pip install -e .` is editable so source edits are picked up
without a reinstall, but Streamlit caches modules per-run so a restart is
still required.

To upgrade Caddy / Litestream binaries, re-run `scripts/setup_server.sh` —
the package installs are idempotent and pinned versions are bumped in the
script itself.

---

## 3. User management

```bash
# Add a user (interactive — prompts for password)
sudo -u wavetest /opt/wavetest-app/.venv/bin/python \
    /opt/wavetest-app/scripts/auth_add_user.py

# Add a user non-interactively
sudo -u wavetest /opt/wavetest-app/.venv/bin/python \
    /opt/wavetest-app/scripts/auth_add_user.py \
    --username jdoe --email jdoe@waveimpact.de --name "John Doe" \
    --password 'someStrongPass' --role analyst

# Promote / demote
sudo -u wavetest /opt/wavetest-app/.venv/bin/python \
    /opt/wavetest-app/scripts/auth_set_role.py --username jdoe --role admin
```

Streamlit picks up changes to `auth/users.yaml` on the next page render — no
restart needed. The daily backup timer will upload the new file the
following morning; trigger an immediate upload with
`sudo systemctl start wavetest-auth-backup.service` after sensitive changes.

---

## 4. Disaster recovery

There are three failure modes worth a runbook entry: lost DB on a healthy
box, lost VM, and lost `auth/users.yaml`.

### 4.1. Restore the SQLite DB in place

```bash
sudo systemctl stop wavetest-app
sudo -u wavetest litestream restore \
    -config /etc/wavetest-app/litestream.yml \
    -o /tmp/wavetest_app.db \
    /opt/wavetest-app/data/wavetest_app.db
sudo -u wavetest mv /opt/wavetest-app/data/wavetest_app.db \
    /opt/wavetest-app/data/wavetest_app.db.broken
sudo -u wavetest mv /tmp/wavetest_app.db /opt/wavetest-app/data/wavetest_app.db
sudo systemctl start wavetest-app
```

To restore a specific point in time, pass `-timestamp 2026-05-15T10:00:00Z`
to the `restore` command. Litestream picks the snapshot at or just before
that wall-clock instant.

### 4.2. Restore on a brand new VM (full DR)

1. Provision a new VM per §1.1.
2. Update DNS to point at the new IP.
3. Clone the repo, copy the secrets into `/etc/wavetest-app/`, run
   `scripts/setup_server.sh`. The script will run Alembic, which creates an
   empty DB. Stop the app before it writes anything important:
   ```bash
   sudo systemctl stop wavetest-app litestream
   ```
4. Restore the SQLite DB from Object Storage:
   ```bash
   sudo -u wavetest rm -f /opt/wavetest-app/data/wavetest_app.db*
   sudo -u wavetest litestream restore \
       -config /etc/wavetest-app/litestream.yml \
       /opt/wavetest-app/data/wavetest_app.db
   ```
5. Restore the most recent `auth/users.yaml`:
   ```bash
   LATEST=$(sudo -u wavetest rclone --config /etc/wavetest-app/rclone.conf \
       lsf hetzner:wavetest-app-backups/auth/ | sort | tail -1)
   sudo -u wavetest rclone --config /etc/wavetest-app/rclone.conf \
       copyto "hetzner:wavetest-app-backups/auth/${LATEST}" \
       /opt/wavetest-app/auth/users.yaml
   ```
6. Start everything:
   ```bash
   sudo systemctl start litestream wavetest-app
   ```

Artefacts (PDF reports etc.) are **not** backed up by Litestream — they're
regenerable from the persisted data on the next assessment run, and storing
them in Object Storage would dominate the bill. If a customer needs an old
report and the box is gone, re-run the assessment.

### 4.3. Lost `auth/users.yaml` only

Restore from the latest dated copy using the rclone command in §4.2 step 5.
If that's gone too, bootstrap a fresh admin user with
`scripts/auth_add_user.py --role admin`; existing user rows in the DB
(audit_log actors etc.) remain valid as references but those users will
need to be re-created in `users.yaml` to log back in.

---

## 5. Monitoring

For 1–3 analysts the minimum sufficient setup is:

- **Uptime check** — UptimeRobot's free tier hits
  `https://wavetest.waveimpact.de` every 5 minutes and emails on failure.
- **`journalctl -u wavetest-app -f`** when actively debugging.
- **`systemctl status wavetest-app litestream caddy`** for a quick health
  snapshot.

The audit log inside the app (admin → 📋 Audit Log) covers all assessment
runs; it's not an infrastructure monitor but it surfaces FAILED rows from
the orchestration layer.

---

## 6. Cost envelope (May 2026)

| Item | Monthly |
| --- | --- |
| CPX21 VM | €5.83 |
| Hetzner backup (VM image) | €1.20 |
| Object Storage (≤1 TB) | €5.99 base + €0.0049/GB egress |
| Domain (`waveimpact.de`) | — (existing) |
| **Total** | **~€13/mo** |

Object Storage egress only matters on restore — replication uploads are
free, snapshots are tiny.
