# Changelog

## Unreleased

### Added

- Adds a persistent Light, Dark, and System theme selector to the main workspace and sign-in screen.
- Adds a focused job-detail dialog with the complete description, fit evidence, work schedule, source, date, and original-listing link.
- Adds an idempotent release workflow that turns published GitHub Release notes into an automated changelog pull request.

### Changed

- Simplifies Job Review cards to the information needed for scanning and moves dense metadata into the detail view.
- Refreshes shared colors, spacing, controls, focus states, tables, cards, and responsive layouts with accessible design tokens.
- Makes the complete job card keyboard-operable while keeping decision actions independent.
- Moves language and theme preferences from the sidebar footer into a dedicated Settings → Interface page.
- Replaces expandable sidebar groups with a flatter, quieter navigation structure that exposes destinations directly.
- Reorganizes sidebar destinations under Control Panel, Jobs, Job Review, Settings, and Administration.
- Redesigns the sidebar as a true top-level and collapsible submenu hierarchy with clearer active states.
- Raises Light and Dark theme text, border, control, and status contrast, with stronger Dark-mode readability.

## 19.1.3

### What's Changed
* Redesign sidebar with hierarchical navigation by @emnl51 in https://github.com/emnl51/bert/pull/74


**Full Changelog**: https://github.com/emnl51/bert/compare/19.1.2...19.1.3

[GitHub Release](https://github.com/emnl51/bert/releases/tag/19.1.3)

## 19.0.0 — Application Workspace

### Added

- Adds responsive Kanban and list views for the complete application pipeline.
- Adds next actions, due dates, contacts, overdue indicators, and an owner-scoped activity timeline.
- Adds manual public-vacancy capture with Search Profile-specific Job Fit and Language Fit scoring.
- Adds application-stage and source-progression analytics.
- Adds an explicit Markdown export for handing a selected vacancy to career-ops without automatic transmission.

### Security

- Keeps application events, analytics, and exports scoped to the authenticated workspace owner.
- Treats exported vacancy descriptions as untrusted input and tells downstream AI tools not to invent qualifications.
- Warns users not to paste private correspondence or credentials into manually captured vacancy text.

### Migration

- Adds the application workspace columns, indexes, and event table in place while preserving existing applications.

## 18.2.7 — Settings Startup Stability

### Fixed

- Prevents the initial settings refresh from writing into controls before their page fragment exists.
- Keeps page reloads from failing with null-element JavaScript errors.

## 18.2.6 — Provider Analytics and Job Loading

### Changed

- Hardens provider funnel analytics against incomplete or unexpected provider records.
- Modernizes job loading so the review workspace remains responsive and safely handles missing elements.

## 18.2.5 — Job Review Startup Stability

### Fixed

- Removes the initial Job Review refresh race that could render results before the jobs table was mounted.
- Makes repeated page refreshes safe when optional UI fragments are not active.

## 18.2.4 — Kleinanzeigen Filter Analytics

### Added

- Adds Kleinanzeigen rejection and acceptance counts to provider analytics.
- Exposes the provider's location, age, employment-format, and parsing funnel for troubleshooting low result counts.

## 18.2.3 — Kleinanzeigen Location Precision

### Fixed

- Rejects Kleinanzeigen listings outside the explicitly configured city or area.
- Keeps city validation separate from the radius setting so a Berlin search does not admit unrelated cities.

## 18.2.2 — Kleinanzeigen Search and Job Cards

### Changed

- Expands active Kleinanzeigen search coverage while retaining conservative request limits.
- Categorizes work schedule, employment type, address, language, publication date, and description data for existing job cards.
- Improves job-card metadata display and provider diagnostics.

### Fixed

- Aligns provider regression tests and CI formatting checks with the richer metadata model.

## 18.2.1 — Kleinanzeigen Profile Compatibility

### Added

- Adds full-time and part-time selection to Kleinanzeigen source configuration.
- Adds configurable listing-age windows such as the last week or last month.

### Changed

- Maps Search Profile phrases, target roles, work arrangements, and language preferences to Kleinanzeigen searches.
- Filters stale or inactive listings and normalizes location, employment format, address, language, and job-type signals.

## 18.2.0 — Experimental Kleinanzeigen Jobs Source

### Added

- Adds an opt-in Kleinanzeigen Jobs provider with conservative paging, request delays, and safe failure handling.
- Parses public job listing links and content into Bert's common job record format.

### Maintenance

- Updates Python requirements and automated dependency versions used by CI and container builds.

## 18.1.1 — Guided Search Profile Builder

### Added

- Adds a step-by-step profile guide for target positions, roles, working arrangements, language level, provider phrases, and scoring keywords.
- Helps users express full-time, part-time, Minijob, and qualification-level preferences in provider-compatible terms.

## 18.1.0 — Profile-Aware Search and Release Updates

### Changed

- Improves position, role, working-time, and language matching across provider search, filtering, and scoring.
- Refines the job-list and job-card UI for clearer fit evidence and faster review.
- Makes the source updater aware of Git release tags even when a release does not add a new commit.
- Applies the resolved release version to source-built containers and the UI.

## 18.0.1 — Release-Aware Updater and Navigation

### Added

- Displays the installed and available GitHub Release versions in the update interface.
- Detects release tags independently from branch commit distance.

### Changed

- Repairs the restricted host updater connection and release-version build propagation.
- Refines the sidebar and responsive navigation for clearer workspace grouping.
- Hardens GitHub workflow permissions for CodeQL and release publishing.

## 18.0.0 — Profile-Scoped Applications

### Added

- Separates Applications by Search Profile so each job-search strategy has its own pipeline.

### Changed

- Strengthens user-workspace isolation across application and profile operations.
- Updates dependency and GitHub Action versions and expands regression coverage.

## 17.2.2 — Multi-User Workspaces and Matching Quality

### Added

- Adds an admin-only **System Email** settings page for configuring account activation emails from the web interface.
- Adds controls for the public base URL, activation-link lifetime, SMTP server, port, username, password, STARTTLS and sender address.
- Adds a test-email function for validating the saved system SMTP configuration.
- Keeps existing `SYSTEM_SMTP_*` environment variables as fallback configuration.

### Security

- Prevents a registered-user session from being elevated by a legacy Basic Auth header.
- Starts newly activated accounts with an empty private workspace instead of seeded profiles and searches.
- Encrypts the system SMTP password at rest using `APP_SECRET_KEY`.
- Never returns the saved SMTP password through the API or displays it in the web interface.
- Preserves the existing password when the password field is left blank.
- Restricts system email settings and test operations to administrators.
- Records system email configuration changes in the audit log.

## 17.2.0 — Multi-User Workspaces and Matching Quality

### Added

- Adds an administrator-only System Email page for activation-link URL, lifetime and SMTP configuration, including encrypted password storage and test delivery.
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

## 17.1 — Account Recovery and Workspace Isolation

### Added

- Adds database recovery tooling and registered-user account support.
- Adds per-user isolation for profiles, searches, decisions, applications, and related workspace data.

### Changed

- Includes the internal `17.0.1` metadata-alignment change that was not published as a separate Git tag.

## 17.0.1 (untagged) — Release Metadata Alignment

### Fixed

- Aligns the application, health endpoint and runtime UI version with the `17.0.1` release.
- Restores the missing changelog history for `16.8`, `16.8.1`, `16.8.2` and `17.0.0`.
- Updates the tagged-image and current-version examples in the README.
- Blocks release-container publishing when the release tag does not match `app/version.py`.

## 17.0.0 — Bert Branding

- Completes the public-facing rename from JobTrack to Bert.
- Reads the sidebar product name from `APP_NAME` instead of hard-coding the legacy name.
- Reads the complete sidebar version from the backend instead of displaying a fixed major version.
- Keeps the application title, health response and navigation shell on one centralized version source.

## 16.8.2 — Bert Deployment Rename and CI Expansion

- Renames the Docker service, container user, persistent volume and deployment examples from JobTrack to Bert.
- Updates GHCR and source-installation examples for the Bert repository and image.
- Adds CodeQL analysis and an additional Docker image build workflow.
- Aligns release-container and update-management tests with the renamed deployment resources.
- Applies Ruff formatting fixes required by the expanded CI checks.

## 16.8.1 — Release Automation

- Adds a GitHub Actions workflow that builds Python release distributions when a GitHub Release is published.
- Uploads the built distributions as workflow artifacts and prepares them for trusted PyPI publishing.

## 16.8 — Security and Configuration Hardening

- Adds per-client failed-login rate limiting with temporary blocking after repeated failures.
- Adds same-origin protection for state-changing browser requests.
- Restricts the SQLite database, WAL and shared-memory files to owner-only permissions when possible.
- Restores a complete `.env.example` with the supported application configuration.

## 16.7 — Jobs Workspace and Grouped Navigation

- Reorganizes navigation into Dashboard, Jobs, Intelligence, Settings and Administration groups.
- Replaces the Search Job modal with a searchable Jobs list and full-page editor.
- Keeps general, search, filter, source, notification and schedule settings on one page.
- Makes profile inheritance explicit for location, search queries, score thresholds, allowlist and blacklist.
- Adds per-job allowlist boosts that can only increase Job Fit.
- Adds per-job and profile blacklists as hard exclusions before scoring, storage and notification.
- Adds Candidate Profile assignment to the same Job editor.
- Preserves existing Search Jobs and migrates legacy profile negative terms into the profile blacklist.

## 16.6 — Maintenance Cleanup

### Changed

- Removed unused duplicate `log_buffer.py`; the active in-memory log system is `log_store.py`.
- Fixed an invalid type annotation in profile storage (`params: [Any]` → `params: list[Any]`).
- Clarified the purpose of the legacy `DEFAULT_KEYWORDS` seed data.

## 16.5 — Job-ad Language Detection

- Detects the dominant language of each job ad as German, English, mixed or unknown.
- Weights the description more strongly than the title and stores a confidence value.
- Adds profile preferences and dashboard filters for job-ad language without deleting excluded jobs.
- Supports manual correction and preserves it when a provider refreshes the job.
- Backfills language metadata for existing jobs during database initialization.

## 16.4 — Hybrid CV Intelligence

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

## 16.3.0 (untagged) — StepStone Experimental Source

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
