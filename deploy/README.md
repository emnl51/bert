# Web update management

JobTrack's web container never receives the Docker socket or Git write access. A small host-side agent owns those privileges and exposes only three authenticated operations over a Unix socket: status, check and update.

The update sequence is fixed:

1. fetch the configured remote branch
2. reject diverged branches or tracked local changes
3. create a consistent SQLite backup in `/data/backups`
4. fast-forward the configured branch
5. rebuild only the `tracker` service
6. restart it and verify `/health`

The agent accepts no shell command, repository path, branch, Compose service or URL from the browser.

## One-time server setup

Run these commands from the JobTrack checkout. Replace the public health URL if needed.

```bash
cd ~/jobtrack

cp deploy/docker-compose.server.yml.example docker-compose.server.yml

UPDATE_AGENT_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"

sudo install -m 0644 deploy/jobtrack-updater.service /etc/systemd/system/jobtrack-updater.service

sudo tee /etc/jobtrack-updater.env >/dev/null <<EOF
JOBTRACK_REPO_DIR=/home/ubuntu/jobtrack
JOBTRACK_BRANCH=main
JOBTRACK_SERVICE=tracker
JOBTRACK_COMPOSE_FILES=docker-compose.yml,docker-compose.server.yml,docker-compose.updater.yml
JOBTRACK_HEALTH_URL=https://jobtakip.duckdns.org/health
JOBTRACK_UPDATE_SOCKET=/run/jobtrack-updater/updater.sock
JOBTRACK_UPDATE_STATE_FILE=/var/lib/jobtrack-updater/status.json
JOBTRACK_UPDATE_TOKEN=$UPDATE_AGENT_TOKEN
EOF
sudo chmod 600 /etc/jobtrack-updater.env

printf '\nUPDATE_AGENT_SOCKET=/run/jobtrack-updater/updater.sock\nUPDATE_AGENT_TOKEN=%s\n' "$UPDATE_AGENT_TOKEN" >> .env

sudo systemctl daemon-reload
sudo systemctl enable --now jobtrack-updater

docker compose \
  -f docker-compose.yml \
  -f docker-compose.server.yml \
  -f docker-compose.updater.yml \
  up -d --build tracker
```

Use the same three Compose files for subsequent manual operations. Keep `docker-compose.yml` tracked and clean; server-specific Caddy/proxy changes belong in the ignored `docker-compose.server.yml` overlay.

Verify the agent and container socket mount:

```bash
sudo systemctl status jobtrack-updater --no-pager
docker compose \
  -f docker-compose.yml \
  -f docker-compose.server.yml \
  -f docker-compose.updater.yml \
  exec tracker test -S /run/jobtrack-updater/updater.sock
```

Open **Updates** in the web UI and select **Check for updates**. The apply button is enabled only when the local branch is clean, not ahead or diverged, and the configured remote branch has newer commits.

## Security notes

- Keep `/etc/jobtrack-updater.env` readable only by root (`chmod 600`).
- Never mount `/var/run/docker.sock` into the JobTrack web container.
- Keep HTTPS and Basic Auth enabled for the admin UI.
- The Unix socket is reachable only inside the host and the JobTrack container; its bearer token is additionally required.
- Update POST requests require a same-origin browser request and an explicit action header.
