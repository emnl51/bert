# Upgrade JobTrack v5 → v6

v6 adds the Target Company Monitor and a refreshed Sources UI. No database schema migration is required.

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
```

Then open the web UI and go to **Sources**.

You should see:

- **Add a company careers page**
- **Configured sources**
- **Source Catalog**
- AUTO / FEED / MANUAL source badges

## Target company detection

Paste a careers/jobs URL and optionally a company name.

Automatically monitored when detected:

- Greenhouse
- Lever
- SmartRecruiters

Recognised but stored as manual shortcuts:

- Workday
- Teamtailor
- Recruitee
- SAP SuccessFactors
- Personio
- Workable
- JOIN
- unknown/company-owned careers pages

Manual shortcuts are intentionally not scraped.

## Data safety

Keep your existing `.env` and Docker `/data` volume. Existing jobs, language scores, source settings, decisions and application history are preserved.
