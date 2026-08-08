# Upgrade JobTrack v3 → v4

v4 adds language-aware matching while preserving existing jobs, decisions, applications, sources, keywords and notification settings.

## Upgrade

Keep your existing Docker volume and replace the application code, then run:

```bash
docker compose up -d --build
```

On startup JobTrack creates a separate `job_language` table for:

- `language_score`
- `overall_score`
- `language_label`
- `language_reasons_json`

The existing `jobs` table is not altered. Existing jobs remain visible immediately; until they are fetched again they use the previous role score as Overall Fit, a neutral Language Fit of 55, and `Language unclear`.

On the next rescan, JobTrack analyses the current job description and stores the new language classification and Overall Fit in `job_language`.

The upgrade also adds the v4 Language Profile settings with safe defaults and seeds English-oriented search phrases once.

## Recommended first step

Open **Search & Schedule → Language profile** and verify:

```text
Primary working language: English
Current German: A2 → B1
Maximum preferred requirement: B1
Minimum Language Fit: 40
Language weight: 35%
Show B2 stretch roles: enabled
Hide C1/fluent/native roles: enabled
Prefer German-growth: enabled
```

Then run **Run search now** once to refresh stored jobs with language scores.
