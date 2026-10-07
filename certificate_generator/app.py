"""FastAPI endpoints and durable SQLite job state."""

import re
import os
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from .pdf import generate_pdf


class JobRequest(BaseModel):
    course: str = Field(min_length=1, max_length=200)
    issue_date: date
    recipients: list[Any] = Field(min_length=1, max_length=1000)

    @field_validator("course")
    @classmethod
    def valid_course(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError("course must contain printable text")
        return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_recipient(value: Any) -> tuple[dict[str, str] | None, str | None]:
    if not isinstance(value, dict):
        return None, "Recipient must be an object"
    name = value.get("name")
    email = value.get("email")
    recipient_id = value.get("recipient_id")
    if (not isinstance(name, str) or not name.strip() or len(name.strip()) > 200
            or any(ord(char) < 32 for char in name)):
        return None, "name must be a nonempty string of at most 200 characters"
    if (not isinstance(email, str) or len(email) > 254
            or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)):
        return None, "email must be a valid email address"
    if recipient_id is not None and (not isinstance(recipient_id, str)
                                  or not recipient_id.strip() or len(recipient_id) > 100):
        return None, "recipient_id must be a nonempty string of at most 100 characters"
    return {"name": name.strip(), "email": email,
            "recipient_id": recipient_id.strip() if recipient_id else ""}, None


def create_app(storage_dir: Path | str = "data") -> FastAPI:
    storage_dir = Path(storage_dir).resolve()
    storage_dir.mkdir(parents=True, exist_ok=True)
    db_path = storage_dir / "jobs.sqlite3"

    def connect() -> sqlite3.Connection:
        db = sqlite3.connect(db_path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    with connect() as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, course TEXT NOT NULL, issue_date TEXT NOT NULL,
                status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS recipients (
                id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
                position INTEGER NOT NULL, name TEXT, email TEXT, external_id TEXT,
                status TEXT NOT NULL, error TEXT, filename TEXT,
                UNIQUE(job_id, position)
            );
            CREATE INDEX IF NOT EXISTS recipients_job_idx ON recipients(job_id);
        """)

    app = FastAPI(title="Bulk Certificate Generator")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    def process_job(job_id: str) -> None:
        with connect() as db:
            db.execute("UPDATE jobs SET status = 'running', updated_at = ? WHERE id = ?",
                       (_now(), job_id))
        with connect() as db:
            pending = db.execute("SELECT * FROM recipients WHERE job_id = ? AND status = 'queued' "
                                 "ORDER BY position", (job_id,)).fetchall()
            job = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        for recipient in pending:
            file_path = storage_dir / "certificates" / job_id / f"{recipient['id']}.pdf"
            temp_path = file_path.with_suffix(".tmp")
            try:
                generate_pdf(temp_path, name=recipient["name"], email=recipient["email"],
                             course=job["course"], issue_date=job["issue_date"],
                             recipient_id=recipient["external_id"] or None)
                temp_path.replace(file_path)
                with connect() as db:
                    db.execute("UPDATE recipients SET status = 'completed', filename = ? "
                               "WHERE id = ?", (str(file_path), recipient["id"]))
            except Exception as exc:
                temp_path.unlink(missing_ok=True)
                with connect() as db:
                    db.execute("UPDATE recipients SET status = 'failed', error = ? WHERE id = ?",
                               (f"Generation failed: {exc}"[:500], recipient["id"]))
        with connect() as db:
            failures = db.execute("SELECT COUNT(*) FROM recipients WHERE job_id = ? AND "
                                  "status = 'failed'", (job_id,)).fetchone()[0]
            db.execute("UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
                       ("completed_with_errors" if failures else "completed", _now(), job_id))

    @app.post("/jobs", status_code=202)
    def create_job(payload: JobRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
        job_id = str(uuid4())
        timestamp = _now()
        with connect() as db:
            db.execute("INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?)",
                       (job_id, payload.course.strip(), payload.issue_date.isoformat(),
                        "queued", timestamp, timestamp))
            for position, raw in enumerate(payload.recipients):
                valid, error = _validate_recipient(raw)
                db.execute("INSERT INTO recipients VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (str(uuid4()), job_id, position, valid["name"] if valid else None,
                            valid["email"] if valid else None,
                            valid["recipient_id"] if valid else None,
                            "failed" if error else "queued", error, None))
        background_tasks.add_task(process_job, job_id)
        return {"job_id": job_id, "status": "queued", "total": len(payload.recipients),
                "status_url": f"/jobs/{job_id}"}

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        with connect() as db:
            job = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if job is None:
                raise HTTPException(404, "Job not found")
            rows = db.execute("SELECT * FROM recipients WHERE job_id = ? ORDER BY position",
                              (job_id,)).fetchall()
        items = [{"id": row["id"], "position": row["position"], "name": row["name"],
                  "email": row["email"], "status": row["status"], "error": row["error"],
                  "download_url": f"/jobs/{job_id}/certificates/{row['id']}"
                  if row["status"] == "completed" else None} for row in rows]
        counts = {state: sum(row["status"] == state for row in rows)
                  for state in ("queued", "completed", "failed")}
        return {"job_id": job_id, "course": job["course"], "issue_date": job["issue_date"],
                "status": job["status"], "total": len(rows), "counts": counts,
                "recipients": items, "created_at": job["created_at"],
                "updated_at": job["updated_at"]}

    @app.get("/jobs/{job_id}/certificates/{recipient_id}")
    def download_certificate(job_id: str, recipient_id: str) -> FileResponse:
        with connect() as db:
            row = db.execute("SELECT status, filename FROM recipients WHERE job_id = ? AND id = ?",
                             (job_id, recipient_id)).fetchone()
        if row is None:
            raise HTTPException(404, "Certificate not found")
        if row["status"] != "completed":
            raise HTTPException(409, "Certificate is not available")
        file_path = Path(row["filename"])
        if not file_path.is_file():
            raise HTTPException(404, "Certificate file is missing")
        return FileResponse(file_path, media_type="application/pdf",
                            filename=f"certificate-{recipient_id}.pdf")

    return app


app = create_app(os.environ.get("CERTIFICATE_DATA_DIR", "data"))
