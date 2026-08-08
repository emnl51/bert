# JobTrack v7

Self-hosted job discovery and application tracker for Berlin/Brandenburg roles, with language-aware ranking, application tracking, extensible sources and feedback-driven search learning.

## v7 highlights: Job Review Queue + Search Learning

The Overview page now acts as a **Job Review Queue**.

Each vacancy shows:

- Overall Fit
- Job Fit
- Language Fit
- language category
- source
- current review state
- current application stage

Review actions:

- **Suitable** — marks the vacancy as suitable and automatically adds it to Application Tracker as `To Apply`.
- **Maybe** — keeps it for later review.
- **Not suitable** — stores a structured rejection reason and can update search learning.

### Not-suitable reasons

- wrong role / function
- German requirement too high
- wrong seniority
- wrong employment type
- wrong location
- not interested in company
- other

The user can disable learning for an individual rejection before saving it.

## Search Learning

JobTrack does not silently rewrite all search keywords after a single rejection. Instead it stores feedback events and creates small, reversible learned penalties.

Examples:

- rejecting a software-development role as `wrong_role` can create a title penalty
- rejecting a company can create a company-specific penalty
- rejecting a location can create a location-specific penalty
- rejecting a German-heavy role can reinforce the language penalty

Learned rules:

- start with a small negative weight
- strengthen gradually when the same signal receives repeated feedback
- are capped to prevent runaway learning
- can be disabled or deleted from the **Learning** page
- are applied to future rescans before the final Overall Fit is calculated

Two new SQLite tables are created automatically:

- `job_feedback`
- `learned_rules`

Existing jobs, applications, language scores and source configuration remain intact.

## Target Company Monitor

Paste a company careers/jobs URL and JobTrack detects supported ATS platforms.

Automatically monitored ATS:

- Greenhouse
- Lever
- SmartRecruiters

Safely recognised as manual shortcuts:

- Workday
- Teamtailor
- Recruitee
- SAP SuccessFactors
- Personio
- Workable
- JOIN
- unknown/company-owned career pages

JobTrack does not bypass site access controls or scrape unsupported platforms.

## Source Catalog

Automatic API/feed sources:

- Arbeitnow
- Adzuna
- Jooble REST API
- Greenhouse Job Board
- Lever postings
- SmartRecruiters company postings
- Custom RSS / Atom

Search-only shortcuts:

- LinkedIn Jobs
- Indeed Germany
- StepStone Germany
- Google job-oriented search
- Glassdoor
- Talent.com
- Bundesagentur für Arbeit Jobsuche

## Language-aware matching

JobTrack ranks each vacancy using:

- **Job Fit (0–100)**
- **Language Fit (0–100)**
- **Overall Fit (0–100)**

Language categories:

- English-first
- German-growth
- B2 stretch
- German-heavy
- Language unclear

Default profile is tuned for English-first work while German progresses from A2 toward B1.

## Application workflow

Application Tracker stages:

`To Apply → Applied → Interview → Rejected / Offer`

Application dates and notes are editable. Review decisions and application history survive later rescans.

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

For v6 → v7, see `UPGRADE_V6_TO_V7.md`. Keep the existing `/data` Docker volume. The feedback schema is created automatically on startup.

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
