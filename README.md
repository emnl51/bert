# JobTrack v10

Self-hosted job discovery, ranking, scheduled search and application tracking for Berlin/Brandenburg roles.

## v10: Multiple Search Jobs

JobTrack now separates **Search Profiles** from **Search Jobs**.

- **Search Profile** = how a vacancy is scored and learned from.
- **Search Job** = an independent automation that decides what to search, where, when, from which sources and how to notify you.

You can create any number of Search Jobs from the web UI.

Examples:

- Werkstudent Berlin — daily at 08:00 — Werkstudent profile — Telegram
- Hennigsdorf Supply Chain — weekly Monday — Werkstudent profile — email
- Full-time Supply Chain Manager — every 12 hours — Full-time profile — Telegram + email
- Target Companies — manual only — selected ATS sources — no notifications

Each Search Job can independently configure:

- scoring profile
- primary location and location terms
- selected sources, or all enabled sources
- weekly / daily / interval / manual-only execution
- day, time and interval
- minimum Overall Fit override
- minimum Language Fit override
- maximum results per notification
- Telegram enabled/disabled
- email enabled/disabled
- Telegram Chat ID override
- Telegram Bot Token override
- SMTP/email recipient/sender overrides
- enabled/disabled state

Blank notification override fields inherit the global notification settings. Per-job secrets are encrypted with the existing `APP_SECRET_KEY`.

### Independent freshness

The same vacancy can legitimately be new to more than one Search Job. v10 therefore stores per-job seen state in `search_job_seen` instead of relying only on global job deduplication. This prevents one Search Job from suppressing another Search Job's notification.

## Search Profiles

Default profiles remain:

- **Werkstudent / Part-time** — Supply Chain, Procurement, Planning, Operations and Logistics student roles; English-first with German A2→B1.
- **Full-time Supply Chain** — Supply Chain Manager, Operations Manager, Procurement Manager, Customer Supply Chain and senior specialist roles.

Each profile has independent scoring, language thresholds and learning rules.

## Learning

Positive learning:

- Suitable
- Applied
- Interview
- Offer

Negative learning comes from structured **Not suitable** reasons. Learning remains profile-specific and reversible.

## Job sources

Automatic API/feed sources:

- Arbeitnow
- Adzuna
- Jooble REST API
- Greenhouse Job Board
- Lever postings
- SmartRecruiters company postings
- custom RSS / Atom

Search-only shortcuts:

- LinkedIn Jobs
- Indeed Germany
- StepStone Germany
- Google job-oriented search
- Glassdoor
- Talent.com
- Bundesagentur für Arbeit Jobsuche

Unsupported sites are not scraped.

## Target Company Monitor

Paste a careers/jobs URL. JobTrack can automatically configure supported Greenhouse, Lever and SmartRecruiters sources and safely store unsupported ATS pages as manual shortcuts.

## Application workflow

`To Apply → Applied → Interview → Rejected / Offer`

Each vacancy can also be reviewed as Suitable, Maybe or Not suitable.

## Database

v10 adds:

- `search_jobs`
- `search_job_runs`
- `search_job_seen`

Existing jobs, profiles, applications, sources, learning rules and settings are preserved.

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

The Docker entry point is now `app.v10_main:app`.

## Upgrade

See `UPGRADE_V9_TO_V10.md`. Keep the existing `/data` Docker volume and keep `APP_SECRET_KEY` unchanged.

## CI

GitHub Actions runs on pushes to `main` and pull requests:

```text
python -m compileall -q app tests
python -m pytest -q
```

## Security

- Keep `.env` out of Git.
- Keep `APP_SECRET_KEY` stable across upgrades.
- Per-search-job bot tokens and SMTP passwords are encrypted in SQLite.
- Do not expose port 8080 publicly without HTTPS or private network access.
- Prefer Caddy/Nginx or Tailscale/WireGuard.
