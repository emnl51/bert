# JobTrack

Self-hosted job search and application tracker for Berlin/Brandenburg Werkstudent and part-time roles in Supply Chain, Procurement, Planning, Order Management, Operations and Logistics.

## v3 highlights

Everything from v2 plus:

- **Apply / Maybe / Skip** decision buttons directly on job results.
- Default **Active** view hides skipped jobs while preserving them in SQLite.
- **Application Tracker** with stages: To Apply → Applied → Interview → Rejected / Offer.
- Choosing **Apply** automatically queues the job in the tracker as **To Apply**.
- Editable application date and notes.
- Application funnel counters on the dashboard.
- Review decisions survive later rescans of the same job.
- v2 database migration is automatic; existing job/search/settings history is preserved.

Existing v2 features remain available:

- Mini admin web UI with HTTP Basic authentication.
- Search target, minimum score and schedule editable without restarting Docker.
- Schedule modes: disabled, every N hours, daily, weekly.
- Built-in sources: Arbeitnow (no key) and Adzuna (API credentials managed from UI).
- Custom RSS/Atom sources.
- Editable ranking/search keywords and weights.
- Telegram and SMTP settings + connection tests.
- API tokens/passwords encrypted in SQLite using `APP_SECRET_KEY`.
- Manual search and run/error history.
- SQLite deduplication.

## Quick start

```bash
cp .env.example .env
```

Generate a strong secret and admin password:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Put different generated values into `ADMIN_PASSWORD` and `APP_SECRET_KEY`, then:

```bash
docker compose up -d --build
```

Open `http://SERVER_IP:8080`. Your browser will request the `ADMIN_USERNAME` / `ADMIN_PASSWORD` from `.env`.

## Review workflow

On **Overview**, each result can be marked:

- **Apply**: creates a row in Application Tracker as `To Apply`.
- **Maybe**: keeps the job for later review.
- **Skip**: hides it from the default Active list, but does not delete it.
- **Clear**: resets the decision to Unreviewed.

## Application Tracker

The **Applications** page supports:

- To Apply
- Applied
- Interview
- Rejected
- Offer

You can edit the stage, application date and notes. When an application first moves beyond `To Apply`, the current timestamp is used as the application date unless you enter a date yourself.

## Upgrade from v2

See `UPGRADE_V2_TO_V3.md`. Keep the same `/data` Docker volume and rebuild the container. Migration is automatic.

## Security notes

- Do not expose port 8080 directly to the public internet without HTTPS.
- Recommended: Caddy/Nginx reverse proxy or private access through Tailscale/WireGuard.
- Keep `APP_SECRET_KEY` stable. Changing it prevents previously saved encrypted secrets from being decrypted until they are re-entered.
- Secret fields are write-only in the UI.

## Tests

```bash
python -m pytest -q
```
