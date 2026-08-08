# JobTrack v9

Self-hosted job discovery, ranking and application tracking for Berlin/Brandenburg roles.

## v9: Multi-profile search

JobTrack can now run multiple career strategies in the same installation. Vacancies are stored once, but each enabled profile gets its own Job Fit, Language Fit and Overall Fit score.

Default profiles:

- **Werkstudent / Part-time** — Supply Chain, Procurement, Planning, Operations and Logistics student roles; English-first with German A2→B1.
- **Full-time Supply Chain** — Supply Chain Manager, Operations Manager, Procurement Manager, Customer Supply Chain and senior specialist roles; prepared for the post-MBA transition.

Each profile has independent:

- search phrases
- title / skill / employment-format scoring weights
- negative keywords
- target location terms
- minimum Overall Fit
- minimum Language Fit
- German level and maximum preferred German requirement
- Language Fit weight
- B2 stretch / German-heavy behaviour
- positive preference learning
- Not-suitable penalty learning

Use **Profiles** in the web UI to create, edit, enable, disable and select profiles. The Job Review Queue has a profile selector and immediately switches to the selected profile's scores and learning rules.

## Profile-aware learning

Learning is isolated per profile. Rejecting a role in the Werkstudent profile does not automatically penalize it in the Full-time profile.

Positive signals:

- Suitable
- Applied
- Interview
- Offer

Negative signals come from structured **Not suitable** reasons. Boost and penalty rules remain visible, reversible and capped.

Application Tracker remains global because an actual application is a single real-world application. Application milestones are learned by the profile where the job was originally marked Suitable; legacy applications without profile history fall back to the default profile.

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

v9 adds:

- `search_profiles`
- `job_profile_scores`
- profile scoping to feedback and learned rules
- profile scoping to positive events and boost rules

Existing jobs, applications, sources and settings are preserved during migration.

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

See `UPGRADE_V8_TO_V9.md`. Keep the existing `/data` Docker volume and `APP_SECRET_KEY`.

## CI

GitHub Actions now runs on pushes to `main` and pull requests:

```text
python -m compileall -q app tests
python -m pytest -q
```

## Security

- Keep `.env` out of Git.
- Keep `APP_SECRET_KEY` stable across upgrades.
- Do not expose port 8080 publicly without HTTPS or private network access.
- Prefer Caddy/Nginx or Tailscale/WireGuard.
