"""Job store using SQLite for local persistence."""

import json
import sqlite3
from typing import Any

from src.config.settings import get_settings


def init_db():
    """Initialize the jobs table."""
    with sqlite3.connect(get_settings().db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                raw_idea TEXT NOT NULL,
                depth TEXT NOT NULL,
                progress_messages TEXT NOT NULL,
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def create_job(job_id: str, raw_idea: str, depth: str):
    """Insert a new pending job."""
    with sqlite3.connect(get_settings().db_path) as conn:
        conn.execute(
            """
            INSERT INTO jobs (job_id, status, raw_idea, depth, progress_messages)
            VALUES (?, ?, ?, ?, ?)
            """,
            (job_id, "pending", raw_idea, depth, "[]"),
        )


def get_job(job_id: str) -> dict[str, Any] | None:
    """Fetch a job by ID."""
    with sqlite3.connect(get_settings().db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        if not row:
            return None
            
        result = dict(row)
        result["progress_messages"] = json.loads(result["progress_messages"])
        if result["result"]:
            result["result"] = json.loads(result["result"])
        return result


def claim_pending_job() -> dict[str, Any] | None:
    """Fetch the oldest pending job and atomically mark it as running."""
    with sqlite3.connect(get_settings().db_path) as conn:
        conn.row_factory = sqlite3.Row
        # Find the oldest pending job
        cursor = conn.execute(
            "SELECT * FROM jobs WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1"
        )
        row = cursor.fetchone()
        if not row:
            return None
            
        # Attempt to claim it atomically
        cursor = conn.execute(
            "UPDATE jobs SET status = 'running', updated_at = CURRENT_TIMESTAMP WHERE job_id = ? AND status = 'pending'",
            (row["job_id"],)
        )
        
        # If rowcount is 0, another worker grabbed it between our SELECT and UPDATE
        if cursor.rowcount == 0:
            return None
            
        result = dict(row)
        result["status"] = "running"
        return result


def update_job_status(job_id: str, status: str, result: dict | None = None):
    """Update a job's status and optionally its final result."""
    result_str = json.dumps(result) if result else None
    with sqlite3.connect(get_settings().db_path) as conn:
        if result_str:
            conn.execute(
                "UPDATE jobs SET status = ?, result = ?, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
                (status, result_str, job_id),
            )
        else:
            conn.execute(
                "UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
                (status, job_id),
            )


def append_progress(job_id: str, new_messages: list[str]):
    """Append new progress messages to the job."""
    if not new_messages:
        return
        
    with sqlite3.connect(get_settings().db_path) as conn:
        cursor = conn.execute("SELECT progress_messages FROM jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        if not row:
            return
            
        messages = json.loads(row[0])
        messages.extend(new_messages)
        
        conn.execute(
            "UPDATE jobs SET progress_messages = ?, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
            (json.dumps(messages), job_id),
        )
