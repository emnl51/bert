# JobTrack v5

Self-hosted job discovery and application tracker. The default profile is tuned for Berlin/Brandenburg Werkstudent and part-time roles in Supply Chain, Procurement, Planning, Order Management, Operations and Logistics.

## v5 highlights: Source Catalog

JobTrack now separates job sources into two modes.

### Automatic API / feed sources

- Arbeitnow
- Adzuna
- Jooble REST API (API key required)
- Greenhouse Job Board API (company board token)
- Lever public postings feed (company/site slug)
- SmartRecruiters company postings (company identifier)
- Custom RSS / Atom feeds

### Search-only shortcuts

- LinkedIn Jobs
- Indeed Germany
- StepStone Germany
- Google job-oriented search
- Glassdoor
- Talent.com
- Bundesagentur für Arbeit Jobsuche

Search-only sources are never scraped. JobTrack stores a search URL template and opens the targeted query in a new browser tab. This avoids pretending that a public job-listing API exists where one is not available or approved.

Use **Sources → Source Catalog** to add or configure providers without editing Python code.

## Language-aware matching

JobTrack scores role fit and language fit separately so English-first jobs are prioritised without losing useful German-growth opportunities.

- **Job Fit (0-100):** role, work format, skills and location.
- **Language Fit (0-100):** English/German requirements detected in the job description.
- **Overall Fit (0-100):** weighted combination of Job Fit and Language Fit.
- **English-first:** English working environment with no mandatory German signal.
- **German-growth:** German is optional or A2/B1-compatible.
- **B2 stretch:** useful roles above the current A2→B1 profile.
- **German-heavy:** C1/fluent/native German signals; hidden from recommended results by default.

## Existing features

- Apply / Maybe / Skip decisions.
- Application Tracker: To Apply → Applied → Interview → Rejected / Offer.
- Editable application dates and notes.
- Admin web UI with HTTP Basic authentication.
- Search location, score thresholds and schedule editable without restarting Docker.
- Telegram and SMTP notifications.
- API tokens/passwords encrypted in SQLite using `APP_SECRET_KEY`.
- SQLite deduplication and run/error history.
- Automatic migration from earlier JobTrack databases.

## Quick start

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
docker compose up -d --build
```

Open `http://SERVER_IP:8080`.

## Upgrade

For v4 → v5, see `UPGRADE_V4_TO_V5.md`. No database migration is required; existing jobs, applications and language scores are preserved.

## Security

- Do not expose port 8080 directly to the public internet without HTTPS.
- Use Caddy/Nginx or private access through Tailscale/WireGuard.
- Keep `APP_SECRET_KEY` stable.
- Secret fields are write-only in the UI.
- `.env` and SQLite database files are excluded by `.gitignore`.

## Tests

```bash
python -m pytest -q
```
