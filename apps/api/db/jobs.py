"""Small SQLite repository. Each operation owns its connection and transaction."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from apps.api.schemas.video import Job, Status, VideoInput


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, input_json TEXT NOT NULL,
                status TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0,
                upstream_task_id TEXT, script TEXT, terms_json TEXT,
                submission_started_at TEXT, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, error TEXT, final_mp4_path TEXT,
                metadata_json TEXT)""")
            db.execute("CREATE INDEX IF NOT EXISTS jobs_status_created ON jobs(status, created_at)")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def create(self, params: VideoInput) -> dict:
        job_id, stamp = str(uuid4()), now()
        with self.connect() as db:
            db.execute("INSERT INTO jobs (id,input_json,status,created_at,updated_at) VALUES (?,?,?,?,?)",
                       (job_id, params.model_dump_json(), Status.RECEIVED.value, stamp, stamp))
        return self.get(job_id)

    def get(self, job_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def list(self, limit: int = 50) -> list[dict]:
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))]

    def pending(self) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE status NOT IN ('COMPLETED','FAILED') ORDER BY created_at LIMIT 1").fetchone()
        return dict(row) if row else None

    def update(self, job_id: str, **fields) -> dict:
        allowed = {"status", "progress", "upstream_task_id", "script", "terms_json",
                   "submission_started_at", "error", "final_mp4_path", "metadata_json"}
        if not fields.keys() <= allowed:
            raise ValueError("Unknown job field")
        fields["updated_at"] = now()
        assignments = ",".join(f"{name}=?" for name in fields)
        with self.connect() as db:
            db.execute(f"UPDATE jobs SET {assignments} WHERE id=?", (*fields.values(), job_id))
        return self.get(job_id)

    @staticmethod
    def public(row: dict) -> Job:
        complete = row["status"] == Status.COMPLETED.value
        return Job(
            id=row["id"], input=VideoInput.model_validate_json(row["input_json"]),
            status=row["status"], progress=row["progress"],
            upstream_task_id=row["upstream_task_id"], created_at=row["created_at"],
            updated_at=row["updated_at"], error=row["error"],
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else None,
            preview_url=f'/api/videos/{row["id"]}/preview' if complete else None,
            download_url=f'/api/videos/{row["id"]}/download' if complete else None,
        )
