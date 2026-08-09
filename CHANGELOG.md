# Changelog

## v16.7.0 — Jobs Workspace and Grouped Navigation

- Reorganizes navigation into Dashboard, Jobs, Intelligence, Settings and Administration groups.
- Replaces the Search Job modal with a searchable Jobs list and full-page editor.
- Keeps general, search, filter, source, notification and schedule settings on one page.
- Makes profile inheritance explicit for location, search queries, score thresholds, allowlist and blacklist.
- Adds per-job allowlist boosts that can only increase Job Fit.
- Adds per-job and profile blacklists as hard exclusions before scoring, storage and notification.
- Adds Candidate Profile assignment to the same Job editor.
- Preserves existing Search Jobs and migrates legacy profile negative terms into the profile blacklist.

## v16.6.0 — Maintenance Cleanup

### Changed

- Removed unused duplicate `log_buffer.py`; the active in-memory log system is `log_store.py` (used by the app and tests).
- Fixed an invalid type annotation in profile storage (`params: [Any]` → `params: list[Any]`).
- Clarified the purpose of the legacy `DEFAULT_KEYWORDS` seed data with a comment pointing to profile-specific keyword sets in `profile_store.py`.

## v16.5.0 — Job-ad Language Detection

- Detects the dominant language of each job ad as German, English, mixed or unknown.
- Weights the description more strongly than the title and stores a confidence value.
- Adds profile preferences and dashboard filters for job-ad language without deleting excluded jobs.
- Supports manual correction and preserves it when a provider refreshes the job.
- Backfills language metadata for existing jobs during database initialization.

## v16.4.1 — Hybrid CV Intelligence

### Added

- Evidence-based CV Match engine with structured requirement extraction
- Seven scoring categories: role, experience, technical skills, tools/software, industry, education/certifications and responsibilities
- Requirement-level `match`, `partial` and `missing` states with CV evidence excerpts
- Hybrid scoring: 70% deterministic evidence + 30% optional Ollama context
- Evidence-linked AI contextual notes and transferable-experience explanations
- Analysis cache keyed by Candidate Profile, job content and AI settings
- Manual **Re-analyze** action in the Intelligence UI
- CV Match score breakdown and detailed evidence viewer
- Configurable Ollama timeout
- Linux Docker host-gateway mapping for `host.docker.internal`

### AI safety / reliability

- Ollama remains disabled by default
- Job descriptions are explicitly treated as untrusted model data
- AI cannot change deterministic requirement match/missing status
- AI context must reference an existing deterministic evidence ID
- Unknown/invented evidence references are discarded
- Ollama failure or timeout falls back to evidence-only scoring
- Scheduled Search Job intelligence runs in a worker thread so model calls do not block the scheduler event loop

### Storage / migration

Existing `job_intelligence` tables are migrated in place with additional JSON evidence, breakdown, cache and AI context fields. Existing Candidate CV encryption remains unchanged.

### Versioning

- Active application version: `16.5.0`
- `/health` and `/api/v16-health` report the active version

## v16.3.0 — StepStone Experimental Source

### Added

- Experimental automated **StepStone Germany** provider
- Dedicated StepStone configuration API and UI
- Conservative request controls: max search terms, pages per term, results per term, timeout and request delay
- StepStone manual-search fallback retained in Source Catalog
- Parsing of StepStone job title, company, location, description snippet, publication text and remote/home-office signal
- Preservation of `Werkstudent`, `Teilzeit`, `Minijob`, `Vollzeit` and hours-per-week signals for the strict employment-format gate
- Parser and catalog regression tests
- `beautifulsoup4` dependency for resilient HTML parsing

### Safety / reliability

- StepStone is disabled until explicitly configured
- No CAPTCHA, proxy or anti-bot bypass is implemented
- HTTP 403/429 is surfaced as a provider error instead of aggressive retrying
- Empty/unparseable result pages fail safely instead of storing malformed jobs
- Requests are sequential and can be delayed to reduce load
- StepStone source testing is automatically constrained to one query and one result page

### Versioning

- Active application version: `16.3.0`
- `/health` and `/api/v16-health` report the same centralized application version

## v16.2.1 — First Public Release

JobTrack's first public release packages the current self-hosted job-search workflow into a Docker-first application with profile-aware filtering, ranking, automation, review and application tracking.

### Highlights

- Responsive desktop, tablet and mobile admin UI
- Search Profiles and independent scheduled Search Jobs
- Job Fit, Language Fit and Overall Fit scoring
- Strict Werkstudent / Part-time / Minijob employment-format filtering
- Application Tracker and review workflow
- Profile-specific positive and negative learning
- Candidate Profiles with encrypted CV text
- CV/job intelligence with deterministic local scoring and optional Ollama support
- Source analytics and quality funnel metrics
- In-app log viewer with filtering and secret redaction
- Database backup, scoped reset and factory reset
- Telegram and email notifications
- Prebuilt release image delivery through GitHub Container Registry (GHCR)

### Job sources

Stable/structured integrations include Arbeitnow, Adzuna, Jooble, Greenhouse, Lever, SmartRecruiters and RSS/Atom feeds.

An experimental JobSpy integration can retrieve jobs from LinkedIn, Indeed, Google Jobs and Glassdoor. JobSpy remains explicitly experimental because scraping reliability can change with upstream rate limits, anti-bot controls and HTML changes.

### Reliability and safety

- Per-query and total JobSpy timeouts
- Provider error secret redaction
- Historical run secret scrubbing
- Persistent SQLite storage under the Docker `/data` volume
- Automatic SQLite snapshot before destructive database reset operations
- Responsive UI compatibility layer for the modern Job Review Queue
- Current public `/health` endpoint reports the active release version
- Python compile, JavaScript syntax and pytest checks in GitHub Actions
- Release image publishing is blocked unless compile, JavaScript syntax and pytest checks pass
- OCI source metadata and build provenance are attached to GHCR images

### Container image

Published releases are pushed to:

```text
ghcr.io/emnl51/jobtrack
```

For this release the workflow creates:

```text
ghcr.io/emnl51/jobtrack:v16.2.1
ghcr.io/emnl51/jobtrack:16.2.1
ghcr.io/emnl51/jobtrack:latest
```

A dedicated `docker-compose.ghcr.yml` file allows deployment without building the application locally.

### Upgrade / deployment

Keep the existing `.env`, `/data` Docker volume and `APP_SECRET_KEY` when updating an existing installation.

Source build:

```bash
cd ~/jobtrack
git pull origin main
docker compose up -d --build
```

Prebuilt GHCR image:

```bash
cd ~/jobtrack
git pull origin main
JOBTRACK_IMAGE_TAG=v16.2.1 docker compose -f docker-compose.ghcr.yml pull
JOBTRACK_IMAGE_TAG=v16.2.1 docker compose -f docker-compose.ghcr.yml up -d
```

Do not use `docker compose down -v` unless persistent volumes are intentionally being deleted.
