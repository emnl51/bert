#!/usr/bin/env python3
"""Host-side, fixed-purpose update agent for JobTrack.

The agent deliberately exposes no command execution API. It only knows how to
check one configured Git branch, back up one JobTrack database, rebuild one
Compose service and verify one health URL.
"""

from __future__ import annotations

import hmac
import json
import os
import re
import socketserver
import subprocess
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def updater_setting(name: str, default: str = "") -> str:
    """Prefer Bert settings while retaining support for older JobTrack installs."""
    return os.environ.get(f"BERT_{name}") or os.environ.get(f"JOBTRACK_{name}") or default


class UpdateFailure(RuntimeError):
    pass


class JobTrackUpdater:
    BUSY_STATES = {"checking", "backing_up", "updating_code", "building", "restarting", "verifying"}

    def __init__(self) -> None:
        self.repo = Path(updater_setting("REPO_DIR", "/home/ubuntu/bert")).resolve()
        self.branch = updater_setting("BRANCH", "main").strip()
        self.service = updater_setting("SERVICE", "bert").strip()
        self.health_url = updater_setting("HEALTH_URL", "http://127.0.0.1:8080/health").strip()
        self.state_file = Path(updater_setting("UPDATE_STATE_FILE", "/var/lib/bert-updater/status.json"))
        self.token = updater_setting("UPDATE_TOKEN")
        compose_names = updater_setting("COMPOSE_FILES", "docker-compose.yml,docker-compose.updater.yml")
        self.compose_files = [self._repo_file(name.strip()) for name in compose_names.split(",") if name.strip()]
        self._lock = threading.RLock()
        self._worker: threading.Thread | None = None
        self.state: dict[str, Any] = {
            "state": "idle",
            "message": "Updater is ready. Check for updates to refresh remote status.",
            "checked_at": None,
            "started_at": None,
            "finished_at": None,
            "update_available": False,
            "safe_to_update": False,
            "deploy_pending": False,
            "log": [],
        }
        self._validate_config()
        self._load_state()
        self._refresh_repo_state(fetch=False)

    def _repo_file(self, name: str) -> Path:
        candidate = (self.repo / name).resolve()
        if candidate != self.repo and self.repo not in candidate.parents:
            raise UpdateFailure(f"Compose file must stay inside the repository: {name}")
        return candidate

    def _validate_config(self) -> None:
        if self.repo == Path("/") or not (self.repo / ".git").exists():
            raise UpdateFailure(f"JOBTRACK_REPO_DIR is not a Git checkout: {self.repo}")
        if not re.fullmatch(r"[A-Za-z0-9._/-]+", self.branch) or self.branch.startswith("-"):
            raise UpdateFailure("JOBTRACK_BRANCH is invalid")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", self.service):
            raise UpdateFailure("JOBTRACK_SERVICE is invalid")
        if len(self.token) < 32:
            raise UpdateFailure("JOBTRACK_UPDATE_TOKEN must contain at least 32 characters")
        missing = [str(path) for path in self.compose_files if not path.is_file()]
        if missing:
            raise UpdateFailure(f"Compose files do not exist: {', '.join(missing)}")

    def _load_state(self) -> None:
        try:
            saved = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            return
        if isinstance(saved, dict):
            for key in ("deploy_pending", "log", "finished_at"):
                if key in saved:
                    self.state[key] = saved[key]
            if saved.get("state") in self.BUSY_STATES:
                self.state.update(state="failed", message="The updater service restarted during a deployment.")

    def _save_state(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temporary, self.state_file)

    def _set_state(self, state: str, message: str, **values: Any) -> None:
        with self._lock:
            self.state.update(state=state, message=message, **values)
            self._save_state()

    def _log(self, message: str) -> None:
        clean = " ".join(str(message).replace("\x00", "").splitlines()).strip()
        if not clean:
            return
        with self._lock:
            entries = list(self.state.get("log") or [])
            entries.append(f"{utc_now()}  {clean[:500]}")
            self.state["log"] = entries[-100:]
            self._save_state()

    def _run(self, args: list[str], *, timeout: int = 120) -> str:
        process = subprocess.run(
            args,
            cwd=self.repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        output = process.stdout.strip()
        for line in output.splitlines()[-12:]:
            self._log(line)
        if process.returncode != 0:
            raise UpdateFailure(f"Command failed with exit code {process.returncode}: {args[0]} {args[1]}")
        return output

    def _git(self, *args: str, timeout: int = 120) -> str:
        return self._run(["git", "-C", str(self.repo), *args], timeout=timeout)

    def _compose(self, *args: str, timeout: int = 300) -> str:
        command = ["docker", "compose"]
        for path in self.compose_files:
            command.extend(["-f", str(path)])
        command.extend(args)
        return self._run(command, timeout=timeout)

    @staticmethod
    def _version_from_text(text: str) -> str | None:
        match = re.search(r'^(?:DEFAULT_)?VERSION\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
        return match.group(1) if match else None

    def _refresh_repo_state(self, *, fetch: bool) -> dict[str, Any]:
        if fetch:
            self._git("fetch", "--prune", "origin", self.branch, timeout=180)
        remote = f"origin/{self.branch}"
        current_branch = self._git("branch", "--show-current")
        local_sha = self._git("rev-parse", "HEAD")
        remote_sha = self._git("rev-parse", remote)
        counts = self._git("rev-list", "--left-right", "--count", f"HEAD...{remote}").split()
        if len(counts) != 2:
            raise UpdateFailure("Could not compare local and remote Git history")
        commits_ahead, commits_behind = (int(value) for value in counts)
        tracked_changes = self._git("status", "--porcelain", "--untracked-files=no")
        safe = current_branch == self.branch and commits_ahead == 0 and not tracked_changes
        deploy_pending = bool(self.state.get("deploy_pending"))
        local_version = self._version_from_text((self.repo / "app/version.py").read_text(encoding="utf-8"))
        remote_version = self._version_from_text(self._git("show", f"{remote}:app/version.py"))
        values = {
            "branch": current_branch,
            "configured_branch": self.branch,
            "local_sha": local_sha,
            "remote_sha": remote_sha,
            "local_subject": self._git("show", "-s", "--format=%s", "HEAD"),
            "remote_subject": self._git("show", "-s", "--format=%s", remote),
            "local_version": local_version,
            "remote_version": remote_version,
            "commits_ahead": commits_ahead,
            "commits_behind": commits_behind,
            "working_tree_clean": not bool(tracked_changes),
            "safe_to_update": safe,
            "update_available": safe and (commits_behind > 0 or deploy_pending),
        }
        with self._lock:
            self.state.update(values)
            self._save_state()
            return dict(self.state)

    def status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self.state)

    def check(self) -> dict[str, Any]:
        with self._lock:
            if self.state.get("state") in self.BUSY_STATES:
                raise UpdateFailure("An update operation is already running")
        self._set_state("checking", "Fetching the configured remote branch…")
        try:
            state = self._refresh_repo_state(fetch=True)
            if not state["safe_to_update"]:
                message = "Update blocked: the branch diverged, changed, or contains tracked local modifications."
            elif state["update_available"]:
                message = f"Update available: {state['commits_behind']} commit(s) behind."
            else:
                message = "Bert is up to date."
            self._set_state("idle", message, checked_at=utc_now())
        except Exception as exc:
            self._set_state("failed", f"Update check failed: {exc}", checked_at=utc_now(), finished_at=utc_now())
            raise
        return self.status()

    def start_update(self) -> dict[str, Any]:
        with self._lock:
            if self._worker and self._worker.is_alive():
                raise UpdateFailure("An update is already running")
            if not self.state.get("update_available") or not self.state.get("safe_to_update"):
                raise UpdateFailure("No safe update is ready. Run an update check first.")
            self.state.update(
                state="checking",
                message="Update accepted; rechecking the remote branch…",
                started_at=utc_now(),
                finished_at=None,
            )
            self._save_state()
            self._worker = threading.Thread(target=self._perform_update, name="jobtrack-update", daemon=True)
            self._worker.start()
        return self.status()

    def _perform_update(self) -> None:
        started = utc_now()
        self._set_state(
            "checking", "Rechecking the remote branch before deployment…", started_at=started, finished_at=None
        )
        try:
            current = self._refresh_repo_state(fetch=True)
            if not current["safe_to_update"] or not current["update_available"]:
                raise UpdateFailure("The repository is no longer in a safe update state")

            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            backup_path = f"/data/backups/bert-web-update-{stamp}.db"
            backup_code = (
                "import pathlib,sqlite3,sys; "
                "target=pathlib.Path(sys.argv[1]); target.parent.mkdir(parents=True,exist_ok=True); "
                "source=sqlite3.connect('/data/jobs.db'); backup=sqlite3.connect(str(target)); "
                "source.backup(backup); backup.close(); source.close(); print(target)"
            )
            self._set_state("backing_up", "Creating a consistent SQLite backup…")
            self._compose("exec", "-T", self.service, "python", "-c", backup_code, backup_path, timeout=180)
            self._log(f"Database backup created: {backup_path}")

            if current["commits_behind"] > 0:
                self._set_state("updating_code", "Fast-forwarding the configured branch…", deploy_pending=True)
                self._git("merge", "--ff-only", f"origin/{self.branch}", timeout=180)
            else:
                self._set_state("updating_code", "Retrying deployment of the current commit…", deploy_pending=True)

            self._set_state("building", "Building the updated Bert image…", deploy_pending=True)
            self._compose("build", "--pull", self.service, timeout=1800)
            self._set_state("restarting", "Restarting the Bert service…", deploy_pending=True)
            self._compose("up", "-d", "--no-deps", self.service, timeout=300)

            self._set_state("verifying", "Waiting for the health check…", deploy_pending=True)
            self._wait_for_health()
            self._refresh_repo_state(fetch=False)
            self._set_state(
                "succeeded",
                "Update completed and the health check passed.",
                deploy_pending=False,
                update_available=False,
                checked_at=utc_now(),
                finished_at=utc_now(),
            )
            self._log("Deployment completed successfully.")
        except Exception as exc:
            self._log(f"Deployment failed: {exc}")
            self._set_state(
                "failed",
                f"Update failed: {exc}. The database backup was preserved; retry is available.",
                deploy_pending=True,
                update_available=True,
                finished_at=utc_now(),
            )

    def _wait_for_health(self) -> None:
        last_error = "health endpoint did not respond"
        for _ in range(45):
            try:
                with urllib.request.urlopen(self.health_url, timeout=4) as response:  # noqa: S310 - configured admin URL
                    payload = json.loads(response.read().decode("utf-8"))
                    if response.status == 200 and payload.get("status") == "ok":
                        self._log(f"Health check passed: {self.health_url}")
                        return
                    last_error = f"unexpected health response: HTTP {response.status}"
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                last_error = str(exc)
            time.sleep(2)
        raise UpdateFailure(f"Health verification timed out: {last_error}")


class UnixHTTPServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


class UpdateRequestHandler(BaseHTTPRequestHandler):
    server_version = "JobTrackUpdater/1"

    @property
    def updater(self) -> JobTrackUpdater:
        return self.server.updater  # type: ignore[attr-defined]

    def _authorized(self) -> bool:
        supplied = self.headers.get("Authorization", "")
        return hmac.compare_digest(supplied, f"Bearer {self.updater.token}")

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _dispatch(self, method: str) -> None:
        if not self._authorized():
            self._json(401, {"detail": "Unauthorized"})
            return
        try:
            if method == "GET" and self.path == "/v1/status":
                payload = self.updater.status()
            elif method == "POST" and self.path == "/v1/check":
                payload = self.updater.check()
            elif method == "POST" and self.path == "/v1/update":
                payload = self.updater.start_update()
            else:
                self._json(404, {"detail": "Not found"})
                return
            self._json(202 if self.path == "/v1/update" else 200, payload)
        except UpdateFailure as exc:
            self._json(409, {"detail": str(exc)})
        except Exception as exc:
            self._json(500, {"detail": f"Updater error: {exc}"})

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if int(self.headers.get("Content-Length", "0") or 0) > 1024:
            self._json(413, {"detail": "Request body is too large"})
            return
        self.rfile.read(int(self.headers.get("Content-Length", "0") or 0))
        self._dispatch("POST")

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    updater = JobTrackUpdater()
    socket_path = Path(updater_setting("UPDATE_SOCKET", "/run/bert-updater/updater.sock"))
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    if socket_path.exists():
        socket_path.unlink()
    server = UnixHTTPServer(str(socket_path), UpdateRequestHandler)
    server.updater = updater  # type: ignore[attr-defined]
    os.chmod(socket_path, int(updater_setting("UPDATE_SOCKET_MODE", "0666"), 8))
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
        if socket_path.exists():
            socket_path.unlink()


if __name__ == "__main__":
    main()
