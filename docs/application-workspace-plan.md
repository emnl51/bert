# Bert application workspace plan

## Product boundary

Bert remains the self-hosted discovery, matching, review, and application-tracking workspace. Agentic CV
tailoring, cover-letter generation, company research, and interview preparation can be performed in career-ops
after an explicit user export. Bert does not silently send vacancy, profile, CV, or application data elsewhere.

## Delivered in this change

1. Extend applications with next action, due date, contact, and owner-scoped events.
2. Replace the table-only tracker with responsive Kanban and list views.
3. Add drag-and-drop stage changes, overdue indicators, and an application detail editor.
4. Add manual public-vacancy capture and score it against the selected Search Profile.
5. Add stage totals, due-action count, and source progression analytics.
6. Add a reviewed Markdown handoff for career-ops.
7. Cover existing-database migration, API behavior, export safety, and cross-user isolation with tests.

## Follow-up releases

- Persist normalized salary, seniority, industry, work-authorization, and provider capability metadata.
- Add repost and inactive-listing signals independently from Job Fit.
- Link generated CV and interview artifacts back to an application without storing third-party credentials.
- Consider opt-in inbox status proposals only after a separate privacy and threat-model review.
