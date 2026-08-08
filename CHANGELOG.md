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

### Upgrade / deployment

Keep the existing `.env`, `/data` Docker volume and `APP_SECRET_KEY` when updating an existing installation.

```bash
cd ~/jobtrack
git pull origin main
docker compose up -d --build
```

Do not use `docker compose down -v` unless persistent volumes are intentionally being deleted.
