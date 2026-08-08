# JobTrack v4

Self-hosted job discovery and application tracker. The default profile is tuned for Berlin/Brandenburg Werkstudent and part-time roles in Supply Chain, Procurement, Planning, Order Management, Operations and Logistics.

## v4 highlights: language-aware matching

JobTrack now scores role fit and language fit separately so English-first jobs are prioritised without losing useful German-growth opportunities.

- **Job Fit (0-100):** role, work format, skills and location.
- **Language Fit (0-100):** English/German requirements detected in the job description.
- **Overall Fit (0-100):** weighted combination of Job Fit and Language Fit. Default language weight: 35%.
- **English-first:** English working environment with no mandatory German signal.
- **German-growth:** German is optional, A2/B1-compatible, or the role can help build German while working mainly in English.
- **B2 stretch:** useful roles above the current A2→B1 profile; visible by default but clearly flagged.
- **German-heavy:** C1, fluent, business-fluent or native German signals. Stored in the database but hidden from recommended results and notifications by default.
- **Language unclear:** the description does not provide enough reliable evidence.

The Search & Schedule page includes a **Language Profile** with:

- primary working language
- current German level: A2 / A2→B1 / B1
- maximum preferred German requirement: A2 / B1 / B2
- minimum Language Fit
- Language Fit weight in Overall Fit
- show/hide B2 stretch roles
- hide German-heavy roles from notifications
- preference for German-growth opportunities

English-oriented search phrases are seeded once during the v4 database migration, including queries such as `working student supply chain english` and `werkstudent procurement english`.

## Existing features

- Apply / Maybe / Skip decisions on job results.
- Application Tracker: To Apply → Applied → Interview → Rejected / Offer.
- Editable application date and notes.
- Mini admin web UI with HTTP Basic authentication.
- Search location, score thresholds and schedule editable without restarting Docker.
- Schedule modes: disabled, every N hours, daily, weekly.
- Built-in Arbeitnow source and optional Adzuna source.
- Custom RSS/Atom sources.
- Editable ranking/search keywords and weights.
- Telegram and SMTP notifications with connection tests.
- API tokens/passwords encrypted in SQLite using `APP_SECRET_KEY`.
- SQLite deduplication and run/error history.
- Automatic migration from earlier JobTrack databases.

## Quick start

```bash
cp .env.example .env
```

Generate strong secrets:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Put different generated values into `ADMIN_PASSWORD` and `APP_SECRET_KEY`, then start:

```bash
docker compose up -d --build
```

Open:

```text
http://SERVER_IP:8080
```

Your browser will request the `ADMIN_USERNAME` and `ADMIN_PASSWORD` from `.env`.

## Recommended language profile

For an English-first candidate currently progressing from German A2 toward B1:

```text
Primary working language: English
Current German: A2 → B1
Maximum preferred requirement: B1
Minimum Language Fit: 40
Language weight: 35%
Show B2 stretch roles: Yes
Hide German-heavy roles: Yes
Prefer German-growth: Yes
```

This keeps English-first and A2/B1-compatible opportunities at the top while still surfacing selected B2 roles as stretch opportunities.

## Review workflow

On **Overview**, each result can be marked:

- **Apply**: adds the job to Application Tracker as `To Apply`.
- **Maybe**: keeps the job for later review.
- **Skip**: hides it from the default active list without deleting it.
- **Clear**: resets the decision.

## Application Tracker

Stages:

- To Apply
- Applied
- Interview
- Rejected
- Offer

Application date and notes can be edited from the dashboard.

## Upgrade from v3

See `UPGRADE_V3_TO_V4.md`. Keep the existing `/data` Docker volume and rebuild the container. v4 creates a separate `job_language` table, so the existing `jobs` table and application history are left intact.

## Security

- Do not expose port 8080 directly to the public internet without HTTPS.
- Use Caddy/Nginx or private access through Tailscale/WireGuard.
- Keep `APP_SECRET_KEY` stable. Changing it prevents previously saved encrypted secrets from being decrypted until re-entered.
- Secret fields are write-only in the UI.
- `.env` and SQLite database files are excluded by `.gitignore`.

## Tests

```bash
python -m pytest -q
```
