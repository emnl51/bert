# Bert

Bert is a self-hosted job-search workspace for collecting vacancies, filtering and ranking results, tracking applications, and comparing jobs with candidate CVs.

It supports separate user workspaces, scheduled searches, profile-specific rules, notifications, and an administrator area for system management.

## Features

- Search Profiles and independently scheduled Search Jobs
- Job Fit, Language Fit, Overall Fit, and evidence-based CV Match
- German, English, mixed, and unknown job-ad language detection
- Strict employment-format filtering for full-time, part-time, Werkstudent, and Minijob searches
- Candidate Profiles with encrypted CV text
- Optional local Ollama context for CV analysis
- Review and application workflow: `To Apply → Applied → Interview → Rejected / Offer`
- User-specific learning, notifications, searches, applications, and candidate data
- Admin-managed registration, account activation, sessions, logs, backups, and updates
- Responsive desktop, tablet, and mobile interface
- Persistent SQLite storage in the Docker `/data` volume

## Job sources

Stable integrations:

- Arbeitnow
- Adzuna
- Jooble
- Greenhouse
- Lever
- SmartRecruiters
- RSS and Atom feeds

Experimental integrations:

- JobSpy for LinkedIn, Indeed, Google Jobs, and Glassdoor
- StepStone Germany

Experimental sources can be affected by rate limits, anti-bot controls, or upstream page changes. Bert does not bypass CAPTCHAs or other access controls.

## Quick start

Requirements:

- Docker with Docker Compose
- Port `8080`, or a custom port mapping
- A stable `APP_SECRET_KEY`

Clone the repository and prepare the environment:

```bash
git clone https://github.com/emnl51/bert.git
cd bert
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set at least these values in `.env`:

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=replace-with-a-long-unique-password
APP_SECRET_KEY=replace-with-the-generated-secret
```

Start Bert:

```bash
docker compose up -d --build
```

Open:

```text
http://SERVER_IP:8080
```

Check the deployment:

```bash
docker compose ps
curl http://127.0.0.1:8080/health
```

## Prebuilt GHCR image

The GHCR Compose file uses:

```text
ghcr.io/whojan/bert
```

Run the latest image:

```bash
git clone https://github.com/emnl51/bert.git
cd bert
cp .env.example .env
docker compose -f docker-compose.ghcr.yml pull
docker compose -f docker-compose.ghcr.yml up -d
```

To pin a release, set `BERT_IMAGE_TAG` before running Compose:

```bash
BERT_IMAGE_TAG=<release-version> docker compose -f docker-compose.ghcr.yml up -d
```

Both deployment methods use the persistent `bert_data` volume.

## Initial configuration

After signing in as the administrator:

1. Create or review Search Profiles.
2. Configure job sources under **Sources → Source Catalog**.
3. Create Search Jobs and assign profiles, schedules, and optional Candidate Profiles.
4. Configure personal Telegram or email notifications in the user workspace.
5. Configure account-activation email under **Administration → System Email**.

System email and job-notification email are separate. System email settings can be managed in the admin UI; the `SYSTEM_SMTP_*` values in `.env` remain available as fallback defaults.

## Candidate Profiles and CV Match

Bert extracts job requirements and links each result to CV evidence using `match`, `partial`, or `missing` states.

The default hybrid score combines:

- 70% deterministic evidence
- 30% optional Ollama context

Ollama is disabled by default. When it is enabled, AI can add evidence-linked context but cannot change deterministic requirement states or invent CV evidence. If Ollama fails or times out, Bert falls back to deterministic scoring.

Configure it under **Intelligence → Hybrid CV Match Engine**. The default host endpoint is:

```text
http://host.docker.internal:11434
```

The model must already exist in the configured Ollama installation.

## Updating

Preserve the existing `.env`, Docker volume, and especially `APP_SECRET_KEY`.

Source deployment:

```bash
cd ~/bert
git pull --ff-only origin main
docker compose up -d --build
```

GHCR deployment:

```bash
cd ~/bert
docker compose -f docker-compose.ghcr.yml pull
docker compose -f docker-compose.ghcr.yml up -d
```

Do not run `docker compose down -v` unless you intentionally want to delete persistent data.

The optional web updater performs guarded fast-forward updates through a restricted host service. Setup instructions are in [deploy/README.md](deploy/README.md).

## Data and security

- Keep `APP_SECRET_KEY` stable; changing it can make encrypted credentials and CV data unreadable.
- SMTP passwords and Candidate CV text are encrypted at rest.
- System SMTP passwords are never returned through the API.
- Registration links are single-use and time-limited.
- User-owned records are isolated by account.
- Destructive database operations create a SQLite snapshot under `/data/backups`.
- Do not expose Bert publicly without HTTPS and appropriate network controls.
- Never mount the Docker socket directly into the web container.
- Keep `.env`, database files, and backups out of Git.

## Development

Bert uses Python 3.12. The stable ASGI entry point is `app.application:app`.

Run the test suite:

```bash
python -m pytest --cov --cov-report=term-missing -q
```

Additional CI checks include Python compilation, Ruff lint/format validation, JavaScript syntax checks, Docker image builds, and CodeQL analysis.

See [CHANGELOG.md](CHANGELOG.md) for release history and [LICENSE](LICENSE) for the Apache 2.0 license.
