# Upgrade v4 → v5

v5 adds the Source Catalog and new provider types. No database migration is required because the existing `sources` table already stores generic source type/config/secret data.

```bash
git pull origin main
docker compose up -d --build
```

Existing jobs, decisions, applications, language scores and notification settings remain unchanged.

Search-only providers (LinkedIn, Indeed, StepStone, Google, Glassdoor, Talent.com, Bundesagentur) do not scrape external websites. They open targeted searches in a new tab.
