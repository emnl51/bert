# Bert

Self-hosted job discovery, filtering, ranking, scheduled search, application tracking and CV/job intelligence for configurable target locations.

Bert combines structured job APIs and ATS feeds with optional experimental job-board providers, profile-specific ranking, language and employment-format filtering, preference learning, notifications, analytics and a responsive admin UI.

## Highlights

- Responsive desktop, tablet and mobile admin UI
- Independent **Search Profiles** and scheduled **Search Jobs**
- Grouped Dashboard, Jobs, Intelligence, Settings and Administration navigation
- Full-page Job editor with explicit profile inheritance and per-job overrides
- Job Fit, Language Fit and Overall Fit scoring
- Strict employment-format filtering for Werkstudent / Part-time profiles
- Automatic German/English job-ad language detection with DE, EN, mixed and unknown filters
- Candidate Profiles with encrypted CV text
- **Evidence-based CV Match with optional local Ollama AI context**
- Profile-specific positive and negative preference learning
- Application workflow: `To Apply → Applied → Interview → Rejected / Offer`
- Telegram and email notifications
- Target-company ATS detection
- Source funnel analytics and quality metrics
- In-app log viewer with secret redaction
- Database backup, scoped reset and factory reset
- In-app release/commit tracking and guarded server updates through an optional host agent
- SQLite persistence in the Docker `/data` volume
- Release images published to GitHub Container Registry (GHCR)

## Search model

### Search Profiles

A Search Profile defines target location, search phrases, title/skill/format boosts, negative rules, minimum Job/Language fit, preferred German/English job-ad languages, employment-format expectations, and optional Candidate Profile assignment for intelligent filtering.

Fresh installations seed:

- **Werkstudent / Part-time** — strict student / part-time / Minijob matching
- **Full-time Supply Chain** — full-time Supply Chain / Operations / Procurement roles

For the strict part-time profile, a vacancy must contain a positive employment-format signal such as `Werkstudent`, `Working Student`, `Teilzeit`, `Part-time`, `Minijob` or compatible hours-per-week signals to pass the employment-format gate.

### Search Jobs

A Search Job is an independent automation built on a Search Profile. The profile supplies base location, search, scoring and filtering values. The Job editor can keep those inherited values or replace them with job-specific overrides.

Allowlist matches add positive Job Fit points but never force a vacancy into the results. Blacklist matches are hard exclusions: the vacancy is skipped before scoring, profile storage and notifications.

When a Candidate Profile is assigned, eligible jobs can automatically receive CV Match intelligence and are sorted using CV Match before normal fit scores.

## Job sources

### Stable automatic sources

- Arbeitnow
- Adzuna — credentials required
- Jooble REST API — API key required
- Greenhouse Job Board API
- Lever postings
- SmartRecruiters company postings
- Custom RSS / Atom feeds

### Experimental sources

**JobSpy** can retrieve jobs from LinkedIn, Indeed, Google Jobs and Glassdoor.

**StepStone Germany** is available as a separate experimental provider that reads normal public StepStone search-result pages. It is conservative by design:

- disabled until explicitly configured
- bounded search terms, pages and results
- configurable timeout and delay
- no CAPTCHA, proxy or anti-bot bypass
- HTTP 403/429 is reported instead of aggressively retried
- unparseable page layouts fail safely
- employment signals are preserved for the strict employment gate

A separate **StepStone Germany — Manual search** shortcut remains available as fallback.

Experimental providers can be affected by rate limits, anti-bot controls or upstream page changes. Stable API/ATS sources should remain the base of automated searches.

## Ranking and filtering

A vacancy passes through:

```text
Provider result
    ↓
Employment format
    ↓
Job Fit
    ↓
Language Fit
    ↓
Overall Fit
    ↓
Profile / learned rules
    ↓
CV Match (when a Candidate Profile is assigned)
    ↓
Recommendation / notification
```

## Candidate Profiles and Hybrid CV Match

Candidate Profiles store CV text, structured skills, languages and target roles. CV text is encrypted at rest using `APP_SECRET_KEY`.

Bert v16.4 uses a hybrid CV Match engine:

```text
Final CV Match
= 70% evidence-based deterministic score
+ 30% optional Ollama contextual score
```

The deterministic score is split into seven categories:

| Category | Weight |
| --- | ---: |
| Role / function | 20% |
| Relevant experience | 25% |
| Technical skills | 20% |
| Tools / software | 10% |
| Industry / domain | 10% |
| Education / certifications | 5% |
| Responsibilities similarity | 10% |

Each extracted requirement stores an evidence status:

```text
match
partial
missing
```

and a supporting CV evidence excerpt. A missing requirement stays missing even when AI is enabled.

### Optional Ollama enrichment

Ollama is disabled by default. With Ollama disabled, CV text is not sent to any LLM.

When enabled, Bert sends the Candidate Profile, job text and deterministic evidence table to the configured Ollama endpoint. Job description text is explicitly treated as untrusted data; instructions, tool calls and secrets are filtered before sending.

AI output can add contextual notes and transferable-experience explanations only when they reference an existing deterministic evidence ID. It cannot create a new matched requirement.

If Ollama fails or times out, Bert automatically falls back to the deterministic evidence score.

The Intelligence screen shows:

- Final CV Match
- Evidence score
- AI context score
- Seven-category score breakdown
- Strengths and gaps
- Risks
- Requirement-by-requirement evidence
- Transferable / partial evidence
- AI evidence-linked context notes
- Analysis engine
- Manual **Re-analyze** action

Analysis results are cached using Candidate Profile content, job content and AI settings. Unchanged jobs do not repeatedly call Ollama. Changing the CV, job description, model or AI configuration invalidates the cache.

### Configure Ollama

Open **Intelligence → Hybrid CV Match Engine**.

Default endpoint:

```text
http://host.docker.internal:11434
```

Both Docker Compose files map `host.docker.internal` to the Linux host gateway, so a host-installed Ollama instance can be reached from the Bert container.

Recommended starting configuration:

```text
Enable Ollama: ON
Ollama URL: http://host.docker.internal:11434
Model: gemma3
Timeout: 60 seconds
```

The model must already exist in the configured Ollama installation.

## Learning and applications

Jobs can be reviewed as Suitable, Maybe or Not suitable. Positive and negative preference learning remains profile-specific.

Application stages:

```text
To Apply → Applied → Interview → Rejected / Offer
```

## Source Analytics

Run History includes source-level funnel metrics:

```text
Fetched → Unique → Job Fit → Language Fit → Recommended → New
```

## Logs

The Logs screen captures application/Uvicorn logs in a bounded in-memory buffer with level/logger/text filtering, auto refresh, pause, TXT export and API key/token/password redaction.

The web buffer resets with the container; Docker stdout/stderr remains available through `docker compose logs`.

## Database administration

The Database screen supports scoped cleanup for jobs/applications, run history/analytics, learning and intelligence data, plus operational and factory resets.

A SQLite snapshot is created before destructive resets and stored under `/data/backups` in the persistent Docker volume.

## Quick start — build from source

Requirements:

- Docker with Docker Compose
- port `8080` available, or adjust the mapping

```bash
git clone https://github.com/whojan/bert.git
cd bert
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set strong values in `.env`:

```text
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<strong-password>
APP_SECRET_KEY=<generated-random-secret>
```

Start:

```bash
docker compose up -d --build
```

Open:

```text
http://SERVER_IP:8080
```

## Configure StepStone

Open **Sources → Source Catalog → StepStone Germany — Experimental → Configure**.

Recommended initial configuration:

```text
Maximum search terms: 3
Pages per search term: 1
Maximum results per term: 25
Request timeout: 30 seconds
Delay between requests: 1 second
```

Test before enabling if desired. Once enabled, StepStone can be selected by individual Search Jobs.

## Run the prebuilt GHCR image

Published releases are pushed to:

```text
ghcr.io/whojan/bert
```

Run a tagged image:

```bash
git clone https://github.com/whojan/bert.git
cd bert
cp .env.example .env
BERT_IMAGE_TAG=17.0.1 docker compose -f docker-compose.ghcr.yml pull
BERT_IMAGE_TAG=17.0.1 docker compose -f docker-compose.ghcr.yml up -d
```

Or follow `latest`:

```bash
docker compose -f docker-compose.ghcr.yml pull
docker compose -f docker-compose.ghcr.yml up -d
```

The GHCR deployment uses the same `.env`, persistent `bert_data` volume and Ollama host-gateway mapping.

## Updating an existing installation

Keep the existing `.env`, Docker `/data` volume and especially `APP_SECRET_KEY`.

```bash
cd ~/bert
git pull origin main
docker compose up -d --build
```

Do **not** use `docker compose down -v` unless persistent volumes are intentionally being deleted.

Verify:

```bash
docker compose ps
docker compose exec bert python -c "import app.v16_main; print(app.v16_main.app.version)"
```

Expected current main version:

```text
17.0.1
```

### Manage updates from the web UI

The optional **Updates** screen compares the installed Git commit with the configured remote branch, shows deployment progress and recent updater logs, and can apply a safe fast-forward update.

Docker and Git privileges remain in a fixed-purpose host service; the web container never receives the Docker socket. The host agent creates a SQLite backup, rebuilds only the bert service and verifies the `/health` endpoint.

## Development and CI

Python 3.12 is used by Docker and CI.

```bash
python -m pytest -q
# or
docker compose exec bert python -m pytest -q
```

GitHub Actions checks:

```text
python -m compileall -q app tests
node --check app/*.js
python -m pytest -q
```

The release-container workflow repeats these checks before publishing to GHCR.

## Architecture note

The Docker entry point is:

```text
app.v16_main:app
```

`v10_main.py` through `v15_main.py` are active composition layers, not obsolete upgrade artifacts.

## Data and security

- `.env`, SQLite files and local backups are ignored by Git.
- Keep `APP_SECRET_KEY` stable; changing it can make encrypted credentials and Candidate CV data unreadable.
- Ollama is optional and disabled by default.
- Job descriptions are treated as untrusted data in AI prompts.
- AI cannot promote unsupported requirements to matched evidence.
- JobSpy and StepStone are experimental; use conservative limits and timeouts.
- Do not expose the admin panel directly to the public internet without HTTPS and appropriate network controls.
- Bert now refuses to start while `ADMIN_PASSWORD` or `APP_SECRET_KEY` still uses a published placeholder value.
- For an internet-facing deployment, place the app behind an HTTPS reverse proxy. `Caddyfile.example` includes TLS, security headers and a rate-limit policy (the rate-limit directive requires a custom Caddy build).

## License

Apache License 2.0. See `LICENSE`.
