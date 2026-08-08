# Upgrade JobTrack v7 → v8

v8 adds positive preference learning. Existing data is preserved.

## Upgrade

```bash
cd ~/jobtrack
git pull origin main
docker compose up -d --build
```

Then verify:

```bash
docker compose ps
curl http://127.0.0.1:8080/health
```

The first search run creates/synchronizes the positive-learning schema automatically.

## New tables

- `positive_events`
- `positive_rules`

Existing `jobs`, `applications`, `job_language`, `job_feedback`, `learned_rules`, sources and settings are not replaced.

## Positive signals

- Suitable
- Applied
- Interview
- Offer

Application milestones are imported once per job/status at search-run time. Re-running the same status does not duplicate evidence.

## Verification

After marking a job Suitable or moving an application to Applied/Interview/Offer, run **Run search now** and open **Learning**. BOOST rules and positive-event counters should appear.
