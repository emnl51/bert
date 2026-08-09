# Changelog

## v17.2.0 — Multi-User Workspaces and Matching Quality

### Added

- Adds a dedicated sign-in page for administrators, registered users and new-user registration.
- Adds self-service account registration with single-use, time-limited email activation links.
- Adds Argon2id password hashing, signed administrator sessions and database-backed user sessions.
- Adds administrator controls to enable or disable accounts, revoke active sessions and cancel pending registrations.
- Adds database backup, restore, scoped reset and recovery support for the user-account schema.
- Adds an adjustable minimum CV Match threshold for Search Jobs with an assigned Candidate Profile; the default threshold is `58`.
- Adds English/German role-family matching, including equivalent titles such as `Production Planner` and `Produktionsplaner / Arbeitsvorbereitung`.
- Adds per-run rejection metrics for blocklist, employment format, general fit, language and CV Match filters.

### Changed

- Makes Search Profiles, Search Jobs, Candidate Profiles, decisions, applications, learning records and notification settings user-specific.
- Runs scheduled searches for every account in the correct user, Candidate Profile and notification context.
- Gives registered users access to their own `/app` workspace while keeping Users, Database, Logs, Updates and source administration restricted to administrators.
- Normalizes HTML, Unicode and whitespace before requirement and skill matching.
- Uses word-boundary matching for short skills and tools to prevent false positives such as matching `SAP` inside unrelated words.
- Separates required and preferred job requirements in scoring and in the Intelligence UI.
- Deduplicates equivalent listings across sources and keeps the record with the richer job description.
- Uses deterministic tie-breaking for equally scored results.

### Security

- Prevents account enumeration by returning the same registration response for existing and new email addresses.
- Rate-limits repeated registration requests by email address and client IP.
- Keeps activation links single-use and stores only their token hashes.
- Enforces ownership checks on user-scoped API operations to prevent cross-account IDOR access.
- Keeps legacy data in the administrator workspace during migration instead of exposing it to newly created users.
- Prevents negated phrases such as `no SAP experience`, `without SAP` and `SAP not required` from becoming positive CV or job evidence.

### Migration

- Adds backward-compatible user ownership columns and indexes while preserving existing administrator data.
- Extends backup and recovery validation to the new account and user-scoped tables.

## v17.0.1 — Release Metadata Alignment

### Fixed

- Aligns the application, health endpoint and runtime UI version with the `17.0.1` release.
- Restores the missing changelog history for `16.8`, `16.8.1`, `16.8.2` and `17.0.0`.
- Updates the tagged-image and current-version examples in the README.
- Blocks release-container publishing when the release tag does not match `app/version.py`.

## v17.0.0 — Bert Branding

- Completes the public-facing rename from JobTrack to Bert.
- Reads the sidebar product name from `APP_NAME` instead of hard-coding the legacy name.
- Reads the complete sidebar version from the backend instead of displaying a fixed major version.
- Keeps the application title, health response and navigation shell on one centralized version source.

## v16.8.2 — Bert Deployment Rename and CI Expansion

- Renames the Docker service, container user, persistent volume and deployment examples from JobTrack to Bert.
- Updates GHCR and source-installation examples for the Bert repository and image.
- Adds CodeQL analysis and an additional Docker image build workflow.
- Aligns release-container and update-management tests with the renamed deployment resources.
- Applies Ruff formatting fixes required by the expanded CI checks.

## v16.8.1 — Release Automation

- Adds a GitHub Actions workflow that builds Python release distributions when a GitHub Release is published.
- Uploads the built distributions as workflow artifacts and prepares them for trusted PyPI publishing.

## v16.8 — Security and Configuration Hardening

- Adds per-client failed-login rate limiting with temporary blocking after repeated failures.
- Adds same-origin protection for state-changing browser requests.
- Restricts the SQLite database, WAL and shared-memory files to owner-only permissions when possible.
- Restores a complete `.env.example` with the supported application configuration.

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

- Removed unused duplicate `log_buffer.py`; the active in-memory log system is `log_store.py`.
- Fixed an invalid type annotation in profile storage (`params: [Any]` → `params: list[Any]`).
- Clarified the purpose of the legacy `DEFAULT_KEYWORDS` seed data.

## v16.5.0 — Job-ad Language Detection

- Detects the dominant language of each job ad as German, English, mixed or unknown.
- Weights the description more strongly than the title and stores a confidence value.
- Adds profile preferences and dashboard filters for job-ad language without deleting excluded jobs.
- Supports manual correction and preserves it when a provider refreshes the job.
- Backfills language metadata for existing jobs during database initialization.

## v16.4.1 — Hybrid CV Intelligence

### Added

- Evidence-based CV Match engine with structured requirement extraction.
- Seven scoring categories: role, experience, technical skills, tools/software, industry, education/certifications and responsibilities.
- Requirement-level `match`, `partial` and `missing` states with CV evidence excerpts.
- Hybrid scoring: 70% deterministic evidence and 30% optional Ollama context.
- Evidence-linked AI contextual notes and transferable-experience explanations.
- Analysis cache keyed by Candidate Profile, job content and AI settings.
- Manual **Re-analyze** action in the Intelligence UI.
- CV Match score breakdown and detailed evidence viewer.
- Configurable Ollama timeout.
- Linux Docker host-gateway mapping for `host.docker.internal`.

### AI safety and reliability

- Ollama remains disabled by default.
- Job descriptions are explicitly treated as untrusted model data.
- AI cannot change deterministic requirement match or missing status.
- AI context must reference an existing deterministic evidence ID.
- Unknown or invented evidence references are discarded.
- Ollama failure or timeout falls back to evidence-only scoring.
- Scheduled Search Job intelligence runs in a worker thread so model calls do not block the scheduler event loop.

### Storage and migration

Existing `job_intelligence` tables are migrated in place with additional JSON evidence, breakdown, cache and AI context fields. Existing Candidate CV encryption remains unchanged.

## v16.3.0 — StepStone Experimental Source

### Added

- Experimental automated **StepStone Germany** provider.
- Dedicated StepStone configuration API and UI.
- Conservative request controls for search terms, pages, results, timeout and request delay.
- StepStone manual-search fallback retained in Source Catalog.
- Parsing of title, company, location, description, publication date and remote-work signals.
- Preservation of employment-format signals for strict filtering.
- Parser and catalog regression tests.
- `beautifulsoup4` dependency for resilient HTML parsing.

### Safety and reliability

- StepStone is disabled until explicitly configured.
- No CAPTCHA, proxy or anti-bot bypass is implemented.
- HTTP 403 and 429 responses are surfaced as provider errors.
- Empty or unparseable result pages fail safely.
- Requests are sequential and can be delayed to reduce load.
- Source testing is constrained to one query and one result page.

## v16.2.1 — First Public Release

JobTrack's first public release packages the self-hosted job-search workflow into a Docker-first application with profile-aware filtering, ranking, automation, review and application tracking.

### Highlights

- Responsive desktop, tablet and mobile admin UI.
- Search Profiles and independent scheduled Search Jobs.
- Job Fit, Language Fit and Overall Fit scoring.
- Strict Werkstudent, part-time and Minijob employment-format filtering.
- Application Tracker and review workflow.
- Profile-specific positive and negative learning.
- Candidate Profiles with encrypted CV text.
- Deterministic CV/job intelligence with optional Ollama support.
- Source analytics and quality funnel metrics.
- In-app log viewer with filtering and secret redaction.
- Database backup, scoped reset and factory reset.
- Telegram and email notifications.
- Prebuilt release images through GitHub Container Registry.

### Job sources

Stable integrations include Arbeitnow, Adzuna, Jooble, Greenhouse, Lever, SmartRecruiters and RSS/Atom feeds.

The experimental JobSpy integration can retrieve jobs from LinkedIn, Indeed, Google Jobs and Glassdoor. Its reliability can change because of upstream rate limits, anti-bot controls and HTML changes.

### Reliability and safety

- Per-query and total JobSpy timeouts.
- Provider-error secret redaction.
- Historical-run secret scrubbing.
- Persistent SQLite storage under the Docker `/data` volume.
- Automatic SQLite snapshot before destructive database reset operations.
- Responsive Job Review Queue.
- Public `/health` endpoint reporting the active release version.
- Python compile, JavaScript syntax and pytest checks in GitHub Actions.
- Release-image publishing blocked unless all required checks pass.
- OCI source metadata and build provenance attached to GHCR images.

### Container image

Published releases are pushed to:

\```text
ghcr.io/emnl51/jobtrack
\```

### Upgrade and deployment

Keep the existing `.env`, `/data` Docker volume and `APP_SECRET_KEY` when updating an existing installation.

Source build:

\```bash
cd ~/jobtrack
git pull origin main
docker compose up -d --build
\```

Do not use `docker compose down -v` unless persistent volumes are intentionally being deleted.
