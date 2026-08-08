# JobTrack

Self-hosted job discovery, filtering, ranking, scheduled search, application tracking and job-search intelligence for Berlin/Brandenburg and configurable target locations.

JobTrack combines stable job APIs and ATS feeds with optional experimental job-board providers, profile-specific ranking, language fit, employment-format filtering, learning, notifications and a responsive admin UI.

## Highlights

- Responsive desktop, tablet and mobile admin UI
- Independent **Search Profiles** and scheduled **Search Jobs**
- Job Fit, Language Fit and Overall Fit scoring
- Strict employment-format filtering for Werkstudent / Part-time profiles
- Profile-specific positive and negative preference learning
- Application workflow: `To Apply → Applied → Interview → Rejected / Offer`
- Candidate profiles with encrypted CV text
- CV/job intelligence with deterministic heuristic scoring and optional local Ollama support
- Telegram and email notifications
- Target-company ATS detection
- Source funnel analytics and source quality metrics
- In-app log viewer with filtering and secret redaction
- Database backup, scoped reset and factory reset tools
- SQLite persistence in a Docker `/data` volume
- Release images published to GitHub Container Registry (GHCR)

## Search model

### Search Profiles

A Search Profile defines how jobs are evaluated:

- target location and location terms
- search phrases
- title / skill / format boosts
- negative rules
- minimum Overall Fit
- minimum Language Fit
- German-language preference
- employment-format expectations
- learned preference rules

Fresh installations seed two profiles:

- **Werkstudent / Part-time** — strict student / part-time / Minijob matching
- **Full-time Supply Chain** — full-time Supply Chain / Operations / Procurement roles

For the Werkstudent / Part-time profile, jobs must contain a positive employment-format signal such as `Werkstudent`, `Working Student`, `Teilzeit`, `Part-time`, `Minijob` or a compatible hours-per-week signal. Explicit full-time roles and jobs with an unconfirmed work format are rejected before being stored.

### Search Jobs

A Search Job is an independent automation built on a Search Profile. Each Search Job can configure:

- profile
- location
- selected sources
- manual / interval / daily / weekly schedule
- score overrides
- maximum results
- Telegram and/or email notifications
- per-job notification overrides
- optional Candidate Profile assignment

Per-job secrets inherit global values when blank and are encrypted with `APP_SECRET_KEY` when stored.

## Job sources

### Stable automatic sources

- Arbeitnow
- Adzuna — credentials required
- Jooble REST API — API key required
- Greenhouse Job Board API
- Lever postings
- SmartRecruiters company postings
- custom RSS / Atom feeds

### Experimental sources

**JobSpy** can retrieve jobs from:

- LinkedIn
- Indeed
- Google Jobs
- Glassdoor

**StepStone Germany** is available as a separate experimental direct provider. It reads normal public StepStone search-result pages and extracts job cards into JobTrack. It is intentionally conservative:

- disabled until explicitly configured
- default maximum 3 search terms per run
- default 1 result page per search term
- default maximum 25 jobs per search term
- configurable 10–90 second request timeout
- configurable delay between StepStone requests
- no CAPTCHA, proxy or anti-bot bypass
- HTTP 403/429 is reported as a provider error instead of retried aggressively
- page-layout changes fail safely instead of inserting malformed jobs
- StepStone employment signals such as `Werkstudent`, `Teilzeit`, `Minijob`, `Vollzeit` and hours-per-week text are preserved for JobTrack's strict employment filter

A separate **StepStone Germany — Manual search** source remains available as a fallback when the experimental provider is blocked or the StepStone page structure changes.

Experimental providers can be affected by rate limits, anti-bot controls or upstream HTML changes. Stable API/ATS sources should remain the preferred base of an automated search setup.

### Search-only fallbacks

JobTrack also keeps safe search shortcuts for:

- LinkedIn Jobs
- Indeed Germany
- StepStone Germany
- Google job-oriented search
- Glassdoor
- Talent.com
- Bundesagentur für Arbeit Jobsuche

These open targeted searches in the original service and remain useful when an automated provider is unavailable.

## Target Company Monitor

Paste a company careers URL in **Sources**. JobTrack detects supported ATS platforms and can automatically configure:

- Greenhouse
- Lever
- SmartRecruiters

Other recognised ATS/career pages such as Workday, Teamtailor, Recruitee, SAP SuccessFactors, Personio, Workable and JOIN are kept as safe manual shortcuts unless a supported provider exists.

## Ranking and filtering

A vacancy is evaluated through several gates:

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
Profile rules / learned preferences
    ↓
Recommendation / notification
```

For strict part-time profiles, employment format is a hard gate; language score or learned boosts cannot rescue an incompatible full-time vacancy.

Language labels include:

- English-first
- German-growth
- B2 stretch
- German-heavy
- Language unclear

## Learning and applications

Review jobs as:

- Suitable
- Maybe
- Not suitable

Positive signals can be learned from Suitable, Applied, Interview and Offer events. Negative learning uses structured Not suitable feedback. Learned rules are profile-specific and can be disabled or deleted from the UI.

Application stages are:

```text
To Apply → Applied → Interview → Rejected / Offer
```

## Candidate Profiles and Intelligence

Candidate Profiles store CV text, skills, languages and target roles. CV text is encrypted at rest using `APP_SECRET_KEY`.

When a Candidate Profile is assigned to a Search Job, JobTrack can calculate CV Match, recommendation, strengths, gaps and risks. The default intelligence engine is local and deterministic; optional Ollama settings are available for local LLM-assisted analysis.

## Source Analytics

Run History includes source-level funnel metrics such as:

```text
Fetched → Unique → Job Fit → Language Fit → Recommended → New
```

This makes it possible to compare source quality instead of evaluating providers only by raw volume.

## Logs

The **Logs** screen captures application/Uvicorn logs in a bounded in-memory buffer and supports:

- INFO / WARNING / ERROR / CRITICAL filtering
- logger filtering
- text search
- auto refresh / pause
- clear view
- TXT export
- API key / token / password redaction

The web log buffer is temporary and resets with the container. Docker stdout/stderr logs remain available through `docker compose logs`.

## Database administration

The **Database** screen supports scoped cleanup for jobs/applications, run history/analytics, learning data and intelligence data, plus operational and factory reset modes.

A SQLite snapshot is created before destructive reset operations. Backups are stored under `/data/backups` inside the persistent Docker volume. Factory Reset always creates a backup and then recreates default schemas/configuration.

## Quick start — build from source

Requirements:

- Docker with Docker Compose
- port `8080` available, or adjust the Compose mapping

```bash
git clone https://github.com/emnl51/jobtrack.git
cd jobtrack
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Edit `.env` before first start:

```text
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<strong-password>
APP_SECRET_KEY=<generated-random-secret>
```

Then start JobTrack:

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

Save it disabled first if you want to run **Test** before enabling it. Once enabled, StepStone can be selected by individual Search Jobs like any other automatic source.

For the built-in Werkstudent / Part-time profile, the first provider queries already target student/part-time/minijob roles. StepStone results still pass through the same strict employment-format gate before being stored.

## Run the prebuilt GHCR image

Every published GitHub Release is tested and then published as a Docker image to:

```text
ghcr.io/emnl51/jobtrack
```

A release tag produces a matching image tag plus `latest`.

To run the prebuilt image without building locally:

```bash
git clone https://github.com/emnl51/jobtrack.git
cd jobtrack
cp .env.example .env
```

Set a strong `ADMIN_PASSWORD` and `APP_SECRET_KEY` in `.env`, then run with the release tag you want:

```bash
JOBTRACK_IMAGE_TAG=v16.3.0 docker compose -f docker-compose.ghcr.yml pull
JOBTRACK_IMAGE_TAG=v16.3.0 docker compose -f docker-compose.ghcr.yml up -d
```

To follow the latest published release instead:

```bash
docker compose -f docker-compose.ghcr.yml pull
docker compose -f docker-compose.ghcr.yml up -d
```

The GHCR deployment uses the same persistent `tracker_data` Docker volume and the same `.env` configuration model as the source-build deployment.

If the container package is not public after its first publication, the package owner must change its visibility to **Public** in GitHub Packages before anonymous `docker pull` commands will work.

## Updating an existing installation

Keep the existing deployment directory, `.env`, Docker `/data` volume and especially `APP_SECRET_KEY`.

Source-build deployment:

```bash
cd ~/jobtrack
git pull origin main
docker compose up -d --build
```

Do **not** use `docker compose down -v` unless you intentionally want to delete persistent Docker volumes.

Verify the running application:

```bash
docker compose ps
docker compose exec tracker python -c "import app.v16_main; print(app.v16_main.app.version)"
```

Expected current main version:

```text
16.3.0
```

## Development and CI

Python 3.12 is used by the Docker image and CI.

Run tests locally or inside the container:

```bash
python -m pytest -q
# or
docker compose exec tracker python -m pytest -q
```

GitHub Actions CI performs:

```text
python -m compileall -q app tests
node --check app/*.js
python -m pytest -q
```

The release container workflow repeats those checks before publishing. On a published GitHub Release it logs in to GHCR with the repository `GITHUB_TOKEN`, builds the image, pushes release and `latest` tags, and publishes build provenance metadata.

## Architecture note

The current Docker entry point is:

```text
app.v16_main:app
```

Files such as `v10_main.py` through `v15_main.py` are intentionally retained. They are composition layers: newer versions import and extend the previous application layer. They are therefore active code, not obsolete upgrade artifacts.

Historical `UPGRADE_V*_TO_V*.md` documents have been removed; this README is the maintained installation and operations reference.

## Data and security

- `.env` is ignored by Git.
- SQLite databases and local backup artifacts are ignored by Git.
- Keep `APP_SECRET_KEY` stable; changing it can make encrypted credentials and Candidate CV data unreadable.
- Rotate a provider credential if it has ever appeared in logs or terminal output.
- JobSpy and StepStone are experimental; use conservative result limits and timeouts.
- Do not expose the admin panel directly to the public internet without HTTPS and appropriate network controls.
- Prefer a reverse proxy or private-access solution such as Caddy/Nginx and/or Tailscale/WireGuard.

## License

Apache License 2.0. See `LICENSE`.
