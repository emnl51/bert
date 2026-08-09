# Bert architecture

The stable ASGI entrypoint is app.application:app. Release numbers are held
centrally in app/version.py; deployments must not point directly at a
version-named module.

The application is split into stores, provider adapters, domain services,
schedulers and UI assets. Search scheduling is owned by app/schedulers/.

The v10_main.py through v16_main.py modules are compatibility layers for the
current release and are not extension points. New endpoints should be added to a
domain router and included by the application composition layer. No v17_main
module should be created.

SQLite uses WAL mode, foreign-key enforcement and a 30-second busy timeout.
Search-job execution uses a database lease, so another process cannot execute
the same job while the first lease is active. APScheduler remains in the web
process for this release; each replica still maintains an in-memory schedule.
