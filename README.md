# JobTrack v6

Self-hosted job discovery and application tracker for Berlin/Brandenburg roles, with language-aware ranking, application tracking and extensible job-source management.

## v6 highlights: Target Company Monitor + improved UI

The Sources page now includes a **Target Company Monitor**. Paste a company careers/jobs URL and JobTrack detects common ATS platforms.

### Automatically monitored ATS

- Greenhouse — board token detected from the jobs URL
- Lever — company/site slug detected from the jobs URL
- SmartRecruiters — company identifier detected from the jobs URL

These sources use their public postings interfaces and can run automatically with the scheduler.

### Safely recognised as manual careers shortcuts

- Workday
- Teamtailor
- Recruitee
- SAP SuccessFactors
- Personio
- Workable
- JOIN
- Unknown/company-owned career pages

JobTrack does **not** scrape these sites. If a supported public feed is not available in JobTrack, the careers URL is stored as a safe manual shortcut instead.

The web UI was also refreshed with:

- clearer JobTrack branding and navigation
- persistent last-opened tab
- modern source cards and AUTO / FEED / MANUAL badges
- a dedicated target-company URL workflow
- modal-based source configuration instead of browser prompts
- improved responsive layout for desktop/tablet/mobile
- clearer configured-source state and credential indicators

## Source Catalog

### Automatic API / feed sources

- Arbeitnow
- Adzuna
- Jooble REST API
- Greenhouse Job Board
- Lever postings
- SmartRecruiters company postings
- Custom RSS / Atom

### Search-only shortcuts

- LinkedIn Jobs
- Indeed Germany
- StepStone Germany
- Google job-oriented search
- Glassdoor
- Talent.com
- Bundesagentur für Arbeit Jobsuche

Search-only providers are never scraped. JobTrack opens a targeted search using the configured query and location.

## Language-aware matching

JobTrack ranks each vacancy using three values:

- **Job Fit (0–100):** role, work format, skills and location
- **Language Fit (0–100):** detected English/German requirement
- **Overall Fit (0–100):** weighted Job Fit + Language Fit

Language categories:

- **English-first**
- **German-growth**
- **B2 stretch**
- **German-heavy**
- **Language unclear**

Default profile is tuned for English-first work while German progresses from A2 toward B1.

## Application workflow

- Apply / Maybe / Skip decisions
- Application Tracker: To Apply → Applied → Interview → Rejected / Offer
- editable application dates and notes
- decisions survive later rescans of the same job

## Operations

- configurable search schedule without restarting Docker
- Telegram and SMTP notifications
- encrypted API tokens/passwords in SQLite using `APP_SECRET_KEY`
- SQLite deduplication and run/error history
- automatic migration from earlier JobTrack databases

## Quick start

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
docker compose up -d --build
```

Open:

```text
http://SERVER_IP:8080
```

## Upgrade

For v5 → v6, see `UPGRADE_V5_TO_V6.md`. No database migration is required.

## Security

- Do not expose port 8080 directly to the public internet without HTTPS.
- Prefer Caddy/Nginx or private access through Tailscale/WireGuard.
- Keep `APP_SECRET_KEY` stable.
- Secret fields are write-only in the UI.
- `.env` and SQLite database files are excluded by `.gitignore`.

## Tests

```bash
python -m pytest -q
```
