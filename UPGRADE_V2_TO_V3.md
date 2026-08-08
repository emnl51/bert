# Upgrade v2 → v3

v3 adds job decisions and an application tracker. The SQLite migration runs automatically at startup.

## Preserved data

- Existing jobs and deduplication history
- Search run history
- Sources and RSS feeds
- Keywords and ranking weights
- Telegram / SMTP / Adzuna settings

## New data

- Each job gets a decision: `unreviewed`, `apply`, `maybe`, or `skip`.
- Choosing `apply` creates an Application Tracker row with status `to_apply`.
- Application statuses: `to_apply`, `applied`, `interview`, `rejected`, `offer`.
- Application date and free-text notes are stored per job.

## Upgrade

Keep the existing Docker volume/database and replace the application files with v3, then run:

```bash
docker compose up -d --build
```

On startup v3 adds the new columns/tables in place. No manual SQL migration is required.

## Behavior

- Rescanning an existing job does not reset its Apply / Maybe / Skip decision.
- Changing an `Apply` decision to `Maybe` or `Skip` removes it from the tracker only while it is still `To Apply`.
- Once a job has advanced to `Applied`, `Interview`, `Rejected`, or `Offer`, its application history is preserved even if the job decision is changed later.
