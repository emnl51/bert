# JobTrack v8

Self-hosted job discovery and application tracker for Berlin/Brandenburg roles, with language-aware ranking, application tracking, extensible sources and bidirectional feedback learning.

## v8 highlights: Positive preference learning

JobTrack now learns not only from **Not suitable** decisions, but also from successful user actions and application outcomes.

Positive signals:

- **Suitable** → light positive signal
- **Applied** → stronger positive signal
- **Interview** → strong positive signal
- **Offer** → strongest positive signal

Repeated updates of the same job/status are idempotent and do not inflate the model. Application milestones are cumulative: an `Offer` confirms `Applied + Interview + Offer` once each.

Positive rules can learn affinity for:

- role/title patterns
- Supply Chain / Procurement / Operations skill terms
- English-first or German-growth environments
- specific companies, but only from stronger Interview / Offer outcomes

Boosts are capped so learned preferences cannot overwhelm the explicit Job Fit model.

## Bidirectional Search Learning

The Learning page now displays two rule types:

- **BOOST** — learned from Suitable / Applied / Interview / Offer
- **PENALTY** — learned from Not suitable feedback

Both types show scope, term, weight, evidence count and strongest signal. Every learned rule can be disabled or deleted.

### Negative learning

Structured Not-suitable reasons include:

- wrong role / function
- German requirement too high
- wrong seniority
- wrong employment type
- wrong location
- not interested in company
- other

Negative rules start small, strengthen gradually with repeated evidence and are capped.

### Positive learning

Positive event weights start approximately at:

- Suitable: +4
- Applied: +5
- Interview: +9
- Offer: +14

Repeated evidence strengthens matching slowly. The total learned positive boost applied to one vacancy is capped at +30 Job Fit points.

## Job Review Queue

Each vacancy shows:

- Overall Fit
- Job Fit
- Language Fit
- language category
- source
- current review state
- application stage
- learned boost/penalty reasons when matched

Review actions:

- **Suitable** — adds the vacancy to Application Tracker as `To Apply` and records a positive preference signal.
- **Maybe** — keeps it for later review without learning.
- **Not suitable** — records a structured reason and optionally updates negative learning.

## Learning database

Feedback/learning tables are created automatically:

- `job_feedback`
- `learned_rules`
- `positive_events`
- `positive_rules`

Existing jobs, applications, language scores, sources and settings remain intact.

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

At each search run, new Applied / Interview / Offer milestones are synchronized into positive learning exactly once.

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

For v7 → v8, see `UPGRADE_V7_TO_V8.md`. Keep the existing `/data` Docker volume. Positive-learning tables are created automatically.

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
