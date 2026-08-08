# Upgrade from v1 to v2

v2 is backward-compatible with the existing `jobs.db` volume. On startup it creates the new settings, sources, keywords and run-history tables without deleting stored jobs.

## 1. Back up the Docker volume (recommended)

If you know the volume name:

```bash
docker run --rm -v berlin_supply_chain_tracker_tracker_data:/data -v "$PWD":/backup alpine \
  tar czf /backup/tracker-data-backup.tgz -C /data .
```

Adjust the volume name if Docker Compose created a different prefix.

## 2. Add security variables to `.env`

Keep your existing notification/API variables if you use them, and add:

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<strong-random-password>
APP_SECRET_KEY=<different-strong-random-secret>
```

Generate values with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Use a different generated value for the admin password and app secret key.

## 3. Rebuild

```bash
docker compose down
docker compose up -d --build
```

## 4. Open the UI

Visit `http://SERVER_IP:8080` and sign in with the Basic Auth credentials from `.env`.

Existing `.env` Adzuna/SMTP/Telegram settings remain usable as bootstrap/fallback values. You can re-save them in the UI to move secrets into encrypted SQLite storage.
