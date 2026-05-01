"""Простое файловое хранилище джобов."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"
JOBS_DIR = DATA_ROOT / "jobs"


def new_job_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{ts}-{uuid.uuid4().hex[:6]}"


def job_dir(job_id: str) -> Path:
    return JOBS_DIR / job_id


def save_job(job_id: str, payload: dict[str, Any]) -> None:
    d = job_dir(job_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "job.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def load_job(job_id: str) -> dict[str, Any]:
    return json.loads((job_dir(job_id) / "job.json").read_text())


def save_floorplan(job_id: str, floorplan_bytes: bytes, suffix: str = ".png") -> Path:
    d = job_dir(job_id)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"floorplan{suffix}"
    p.write_bytes(floorplan_bytes)
    return p


def load_floorplan(job_id: str) -> bytes:
    d = job_dir(job_id)
    for name in ("floorplan.png", "floorplan.jpg", "floorplan.jpeg", "floorplan.webp"):
        p = d / name
        if p.exists():
            return p.read_bytes()
    raise FileNotFoundError(f"floorplan not found for job {job_id}")
