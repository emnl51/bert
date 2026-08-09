import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .config import settings
from .db import connection, exclusive_database_access, init_db


class InvalidDatabaseBackup(ValueError):
    pass


class DatabaseRestoreBusy(RuntimeError):
    pass


class DatabaseRestoreFailed(RuntimeError):
    pass


_REQUIRED_SCHEMA = {
    "jobs": {"job_key", "source", "external_id", "title", "url"},
    "app_settings": {"key", "value", "is_secret"},
    "sources": {"id", "name", "source_type", "config_json", "secrets_json"},
    "keywords": {"id", "term", "kind", "weight", "enabled"},
    "applications": {"job_key", "status"},
}

RESET_SCOPES = {
    "jobs": {
        "label": "Jobs & Applications",
        "tables": [
            "job_intelligence",
            "job_feedback",
            "positive_events",
            "job_profile_scores",
            "job_language",
            "search_job_seen",
            "applications",
            "jobs",
        ],
    },
    "runs": {
        "label": "Run History & Analytics",
        "tables": ["source_run_stats", "search_job_runs", "search_runs"],
    },
    "learning": {
        "label": "Learning Data",
        "tables": ["job_feedback", "learned_rules", "positive_events", "positive_rules"],
    },
    "intelligence": {
        "label": "AI / Intelligence Data",
        "tables": ["job_intelligence"],
    },
}


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _backup_directory() -> Path:
    backup_dir = Path(settings.database_path).parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(backup_dir, 0o700)
    return backup_dir


def _snapshot_database(target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(settings.database_path, timeout=30) as src, sqlite3.connect(str(target)) as dst:
            src.execute("PRAGMA busy_timeout = 30000")
            src.backup(dst)
        os.chmod(target, 0o600)
    except Exception:
        target.unlink(missing_ok=True)
        raise


def _safe_app_slug() -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in settings.app_name).strip("-")
    return slug or "bert"


def list_user_tables() -> list[str]:
    with connection() as con:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    return [r["name"] for r in rows]


def database_counts() -> dict[str, int]:
    result = {}
    with connection() as con:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        for row in rows:
            table = row["name"]
            try:
                result[table] = int(con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            except sqlite3.DatabaseError:
                result[table] = -1
    return result


def backup_database() -> str:
    target = _backup_directory() / f"{_safe_app_slug()}-{_now_stamp()}.db"
    with exclusive_database_access():
        _snapshot_database(target)
    return str(target)


def create_download_backup() -> tuple[str, str]:
    """Create a temporary consistent snapshot for an authenticated download."""
    stamp = _now_stamp()
    fd, raw_path = tempfile.mkstemp(prefix=".download-", suffix=".db", dir=_backup_directory())
    os.close(fd)
    target = Path(raw_path)
    try:
        with exclusive_database_access():
            _snapshot_database(target)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return str(target), f"{_safe_app_slug()}-data-{stamp}.db"


def create_restore_staging_file() -> str:
    db_dir = Path(settings.database_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    fd, raw_path = tempfile.mkstemp(prefix=".restore-upload-", suffix=".db", dir=db_dir)
    os.close(fd)
    os.chmod(raw_path, 0o600)
    return raw_path


def remove_temporary_database(path: str) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


def validate_database_backup(path: str | Path) -> dict:
    backup_path = Path(path)
    try:
        size = backup_path.stat().st_size
    except OSError as exc:
        raise InvalidDatabaseBackup("Backup file is not readable") from exc
    if size <= 0:
        raise InvalidDatabaseBackup("Backup file is empty")
    if size > settings.database_restore_max_bytes:
        raise InvalidDatabaseBackup(
            f"Backup exceeds the {settings.database_restore_max_bytes // (1024 * 1024)} MB restore limit"
        )
    try:
        with backup_path.open("rb") as handle:
            if handle.read(16) != b"SQLite format 3\x00":
                raise InvalidDatabaseBackup("Uploaded file is not a SQLite database")
    except OSError as exc:
        raise InvalidDatabaseBackup("Backup file is not readable") from exc

    try:
        uri = f"{backup_path.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=10) as con:
            con.execute("PRAGMA query_only = ON")
            integrity = con.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                detail = integrity[0] if integrity else "no result"
                raise InvalidDatabaseBackup(f"SQLite integrity check failed: {detail}")
            foreign_key_error = con.execute("PRAGMA foreign_key_check").fetchone()
            if foreign_key_error:
                raise InvalidDatabaseBackup("Backup contains invalid foreign-key references")
            tables = {
                row[0]
                for row in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            }
            missing_tables = sorted(set(_REQUIRED_SCHEMA) - tables)
            if missing_tables:
                raise InvalidDatabaseBackup(
                    f"Backup is not a Bert database; missing tables: {', '.join(missing_tables)}"
                )
            for table, required_columns in _REQUIRED_SCHEMA.items():
                columns = {row[1] for row in con.execute(f'PRAGMA table_info("{table}")').fetchall()}
                missing_columns = sorted(required_columns - columns)
                if missing_columns:
                    raise InvalidDatabaseBackup(
                        f"Backup table {table} is missing columns: {', '.join(missing_columns)}"
                    )
    except InvalidDatabaseBackup:
        raise
    except sqlite3.DatabaseError as exc:
        raise InvalidDatabaseBackup(f"SQLite validation failed: {exc}") from exc

    return {"bytes": size, "tables": len(tables), "integrity": "ok"}


def _active_search_job_count() -> int:
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(settings.database_path, timeout=30) as con:
        table = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='search_job_locks'").fetchone()
        if not table:
            return 0
        con.execute("DELETE FROM search_job_locks WHERE expires_at <= ?", (now,))
        return int(con.execute("SELECT COUNT(*) FROM search_job_locks").fetchone()[0])


def _prepare_replacement(source: Path) -> Path:
    db_dir = Path(settings.database_path).parent
    fd, raw_path = tempfile.mkstemp(prefix=".restore-ready-", suffix=".db", dir=db_dir)
    os.close(fd)
    target = Path(raw_path)
    try:
        shutil.copyfile(source, target)
        os.chmod(target, 0o600)
        with sqlite3.connect(str(target), timeout=30) as con:
            con.execute("PRAGMA journal_mode = DELETE")
        with target.open("rb") as handle:
            os.fsync(handle.fileno())
        return target
    except Exception:
        target.unlink(missing_ok=True)
        raise


def _replace_live_database(replacement: Path) -> None:
    db_path = Path(settings.database_path)
    if db_path.exists():
        with sqlite3.connect(str(db_path), timeout=30) as con:
            checkpoint = con.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            if checkpoint and checkpoint[0] != 0:
                raise DatabaseRestoreBusy("Database is busy; wait for current activity and try again")
    for suffix in ("-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    os.replace(replacement, db_path)
    os.chmod(db_path, 0o600)
    directory_fd = os.open(db_path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _clear_transient_runtime_state() -> None:
    with connection() as con:
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "search_job_locks" in tables:
            con.execute("DELETE FROM search_job_locks")
        if "search_job_runs" in tables:
            now = datetime.now(timezone.utc).isoformat()
            con.execute(
                "UPDATE search_job_runs SET status='interrupted',finished_at=?,error=? WHERE status='running'",
                (now, "Interrupted by database restore"),
            )


def restore_database(path: str | Path) -> dict:
    """Validate and atomically restore a Bert SQLite backup.

    The current database is retained as a safety backup. If schema migration or
    final validation fails, that snapshot is restored before the error returns.
    """
    source = Path(path)
    uploaded = validate_database_backup(source)
    replacement: Path | None = None
    with exclusive_database_access():
        active_searches = _active_search_job_count()
        if active_searches:
            raise DatabaseRestoreBusy(
                f"Cannot restore while {active_searches} search job(s) are running; wait for them to finish"
            )
        before = database_counts()
        safety_backup = Path(backup_database())
        replacement = _prepare_replacement(source)
        try:
            _replace_live_database(replacement)
            replacement = None
            _reseed_factory_defaults()
            _clear_transient_runtime_state()
            restored = validate_database_backup(settings.database_path)
            after = database_counts()
        except Exception as exc:
            if replacement is not None:
                replacement.unlink(missing_ok=True)
                replacement = None
            rollback = _prepare_replacement(safety_backup)
            try:
                _replace_live_database(rollback)
                validate_database_backup(settings.database_path)
            except Exception as rollback_exc:
                raise DatabaseRestoreFailed(
                    f"Restore failed and automatic rollback also failed: {rollback_exc}"
                ) from exc
            raise DatabaseRestoreFailed(f"Restore failed; the previous database was restored: {exc}") from exc
        finally:
            if replacement is not None:
                replacement.unlink(missing_ok=True)

    return {
        "ok": True,
        "verified": True,
        "uploaded": uploaded,
        "restored": restored,
        "safety_backup_path": str(safety_backup),
        "before": before,
        "after": after,
    }


def _delete_tables(tables: list[str]) -> dict[str, int]:
    deleted = {}
    # Use an immediate transaction so the destructive reset is atomic with respect
    # to other SQLite writers. This prevents a partial reset from being reported as success.
    con = sqlite3.connect(settings.database_path, timeout=30)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA foreign_keys=OFF")
        con.execute("BEGIN IMMEDIATE")
        existing = {r["name"] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        for table in tables:
            if table not in existing or table.startswith("sqlite_"):
                continue
            count = int(con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            con.execute(f'DELETE FROM "{table}"')
            deleted[table] = count
            try:
                con.execute("DELETE FROM sqlite_sequence WHERE name=?", (table,))
            except sqlite3.DatabaseError:
                pass
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return deleted


def _reseed_factory_defaults() -> None:
    init_db()
    from .profile_store import ensure_profile_schema
    from .search_job_store import ensure_search_job_schema
    from .language_store import ensure_language_schema
    from .feedback_store import ensure_feedback_schema
    from .candidate_store import ensure_candidate_schema
    from .intelligence import ensure_intelligence_schema
    from .source_analytics import ensure_source_analytics_schema
    from .user_store import ensure_user_schema

    ensure_profile_schema()
    ensure_search_job_schema()
    ensure_language_schema()
    ensure_feedback_schema()
    ensure_candidate_schema()
    ensure_intelligence_schema()
    ensure_source_analytics_schema()
    ensure_user_schema()


def _expected_empty_tables(scope: str) -> set[str]:
    if scope == "factory":
        return {
            "jobs",
            "applications",
            "job_intelligence",
            "job_feedback",
            "positive_events",
            "job_profile_scores",
            "job_language",
            "search_job_seen",
            "source_run_stats",
            "search_job_runs",
            "search_runs",
            "learned_rules",
            "positive_rules",
        }
    if scope == "operational":
        out = set()
        for key in ("jobs", "runs", "learning", "intelligence"):
            out.update(RESET_SCOPES[key]["tables"])
        return out
    return set(RESET_SCOPES[scope]["tables"])


def reset_database(scope: str, create_backup: bool = True) -> dict:
    with exclusive_database_access():
        return _reset_database_locked(scope, create_backup)


def _reset_database_locked(scope: str, create_backup: bool = True) -> dict:
    valid = set(RESET_SCOPES) | {"operational", "factory"}
    if scope not in valid:
        raise ValueError("Invalid reset scope")

    backup_path = backup_database() if create_backup else ""
    before = database_counts()

    if scope == "factory":
        tables = list_user_tables()
    elif scope == "operational":
        tables = []
        for key in ("jobs", "runs", "learning", "intelligence"):
            tables.extend(RESET_SCOPES[key]["tables"])
        tables = list(dict.fromkeys(tables))
    else:
        tables = RESET_SCOPES[scope]["tables"]

    deleted = _delete_tables(tables)
    if scope == "factory":
        _reseed_factory_defaults()

    after = database_counts()
    expected_empty = _expected_empty_tables(scope)
    remaining = {table: after.get(table, 0) for table in expected_empty if after.get(table, 0) > 0}
    if remaining:
        raise RuntimeError(f"Reset verification failed; rows remain: {remaining}")

    return {
        "ok": True,
        "verified": True,
        "scope": scope,
        "backup_path": backup_path,
        "deleted": deleted,
        "rows_deleted": sum(deleted.values()),
        "before": before,
        "after": after,
        "remaining": remaining,
    }
