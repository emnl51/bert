# Web update management

Bert's web container never receives the Docker socket or Git write access. A small host-side agent owns those privileges and exposes only three authenticated operations over a Unix socket: stat/health, recent log lines, and guarded safe fast-forward update.

The update sequence is fixed:

1. fetch the configured remote branch
2. reject diverged branches or tracked local changes
3. create a consistent SQLite backup in `/data/backups`
4. fast-forward the configured branch
5. rebuild only the `bert` service
6. restart it and verify `/health`

The agent accepts no shell command, repository path, branch, Compose service or URL from the browser.

## One-time server setup

Run these commands from the Bert checkout. Replace the public health URL if needed.

```bash
cd ~/bert

cp deploy/docker-compose.server.yml.example docker-compose.server.yml

UPDATE_AGENT_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"

sudo install -m 0644 deploy/bert-updater.service /etc/systemd/system/bert-updater.service

sudo tee /etc/bert-updater.env >/dev/null <<EOF
BERT_REPO_DIR=/home/ubuntu/bert
BERT_BRANCH=main
BERT_SERVICE=bert
BERT_COMPOSE_FILES=docker-compose.yml,docker-compose.server.yml,docker-compose.updater.yml
BERT_HEALTH_URL=https://yourdomain.com/health
BERT_UPDATE_SOCKET=/run/bert-updater/updater.sock
BERT_UPDATE_STATE_FILE=/var/lib/bert-updater/status.json
BERT_UPDATE_TOKEN=$UPDATE_AGENT_TOKEN
EOF
sudo chmod 600 /etc/bert-updater.env

printf '\nUPDATE_AGENT_SOCKET=/run/bert-updater/updater.sock\nUPDATE_AGENT_TOKEN=%s\n' "$UPDATE_AGENT_TOKEN" >> .env

sudo systemctl daemon-reload
sudo systemctl enable --now bert-updater

docker compose \
  -f docker-compose.yml \
  -f docker-compose.server.yml \
  -f docker-compose.updater.yml \
  up -d --build bert
```

Use the same three Compose files for subsequent manual operations. Keep `docker-compose.yml` tracked and clean; server-specific Caddy/proxy changes belong in the ignored `docker-compose.server.yml`.

Verify the agent and container socket mount:

```bash
sudo systemctl status bert-updater --no-pager
docker compose \
  -f docker-compose.yml \
  -f docker-compose.server.yml \
  -f docker-compose.updater.yml \
  exec bert test -S /run/bert-updater/updater.sock
```

Open **Updates** in the web UI and select **Check for updates**. The apply button is enabled only when the local branch is clean, not ahead or diverged, and the configured remote branch has newer commits.

## Security notes

- Keep `/etc/bert-updater.env` readable only by root (`chmod 600`).
- Never mount `/var/run/docker.sock` into the Bert web container.
- Keep HTTPS and Basic Auth enabled for the admin UI.
- The Unix socket is reachable only inside the host and the Bert container; its bearer token is additionally required.
- Update POST requests require a same-origin browser request and an explicit action header.
