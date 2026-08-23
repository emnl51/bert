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
- Application workspace with Kanban/list views, follow-up dates, contacts, activity history, and source conversion
- Manual vacancy capture with profile-aware Job Fit and Language Fit scoring
- Explicit Markdown handoff of selected applications to career-ops
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
- Kleinanzeigen Jobs

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

## Application workspace and career-ops handoff

Applications can be managed as a Kanban board or list. Each application stores its stage, application date,
next action, due date, contact, notes, and an owner-scoped activity timeline. The workspace also shows overdue
actions, stage totals, and source progression.

Use **Add job** to capture a public vacancy that was found outside Bert's providers. Bert scores the pasted
vacancy against the selected Search Profile and adds it to **To Apply**. Review the extracted fields before
saving and do not paste private correspondence or credentials into the public vacancy description.

The **Export for career-ops** action downloads a Markdown handoff containing the vacancy, Bert's match evidence,
and the current application state. Nothing is sent automatically. Review the file before sharing it with an AI
CLI or provider; CV tailoring, cover letters, and interview preparation remain explicit career-ops tasks.

## Interface and themes

The workspace uses a responsive, minimalist layout with keyboard-visible focus states and touch-friendly controls.
Choose **System**, **Light**, or **Dark** from the sidebar; the preference is stored only in the browser and System
follows the operating-system color scheme.

Job Review cards show only the role, company, location, Overall Fit, work arrangement, freshness, and review actions.
Select a card—or focus it and press Enter—to open the complete detail view. The original job site opens only from
that view, so scanning the queue does not unexpectedly leave Bert.

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

Every pull request must review and update this README so user-visible behavior, setup steps, and operational
guidance stay aligned with the code. Release-impacting changes must also be recorded under **Unreleased** in
`CHANGELOG.md`.

When a GitHub Release is published, the **Sync release changelog** workflow converts its release notes into an
exact-tag section in `CHANGELOG.md` and opens an automated pull request. The operation is idempotent, so rerunning
the workflow will not create duplicate release entries.

Run the test suite:

```bash
python -m pytest --cov --cov-report=term-missing -q
```

Additional CI checks include Python compilation, Ruff lint/format validation, JavaScript syntax checks, Docker image builds, and CodeQL analysis.

See [CHANGELOG.md](CHANGELOG.md) for release history and [LICENSE](LICENSE) for the Apache 2.0 license.
