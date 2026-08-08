# Changelog

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
