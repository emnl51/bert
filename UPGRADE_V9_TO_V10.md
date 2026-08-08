# Upgrade JobTrack v9 → v10

v10 introduces independent **Search Jobs** on top of Search Profiles.

## What changes

New tables are created automatically:

- `search_jobs`
- `search_job_runs`
- `search_job_seen`

Existing jobs, applications, search profiles, source configuration, learning rules and secrets are preserved.

The Docker entry point changes from:

```text
app.main:app
```

to:

```text
app.v10_main:app
```

The old single scheduled search is removed from the in-process scheduler after startup. Search Jobs become the scheduling source of truth. Manual legacy endpoints remain available for backward compatibility.

## Upgrade

```bash
cd ~/jobtrack
git pull origin main
docker compose up -d --build
```

Verify:

```bash
docker compose ps
curl http://127.0.0.1:8080/health
curl -u "$ADMIN_USERNAME:$ADMIN_PASSWORD" http://127.0.0.1:8080/api/v10-health
```

The second endpoint should report version `10.0.0` and the number of Search Jobs scheduled.

## First migration behavior

If no Search Job exists, JobTrack seeds one default job named:

```text
Werkstudent Berlin Weekly
```

It uses the default search profile and all currently enabled automatic sources. Notifications are off until configured in the Search Jobs UI.

## Notification inheritance

Each Search Job can enable Telegram and/or email separately.

Blank per-job notification fields inherit the global settings. Per-job Bot Tokens and SMTP passwords are encrypted using the existing `APP_SECRET_KEY`.

Do not change `APP_SECRET_KEY` during the upgrade.

## Data safety

Keep the existing Docker `/data` volume. Do not delete the SQLite database before upgrading.
