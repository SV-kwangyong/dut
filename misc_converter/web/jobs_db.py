"""잡 이력 저장소 — sqlite3(표준 라이브러리). 변환 진행 상태의 진실은 산출물(무상태 검증)이고, 여기는 감사·이력용."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    adapter TEXT NOT NULL,
    inputs TEXT NOT NULL,
    options TEXT NOT NULL,
    output_dir TEXT,
    flags TEXT NOT NULL,
    status TEXT NOT NULL,
    progress_done INTEGER NOT NULL DEFAULT 0,
    progress_total INTEGER NOT NULL DEFAULT 0,
    summary TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);
"""


class JobsDB:
    def __init__(self, path: Path | str) -> None:
        self._path = str(path)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self._path, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    def insert(self, job: dict[str, Any]) -> None:
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO jobs (id, adapter, inputs, options, output_dir, flags, status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job["id"],
                    job["adapter"],
                    json.dumps(job["inputs"], ensure_ascii=False),
                    json.dumps(job["options"], ensure_ascii=False),
                    job.get("output_dir"),
                    json.dumps(job["flags"], ensure_ascii=False),
                    job["status"],
                    job["created_at"],
                ),
            )

    def update(self, job_id: str, **fields: Any) -> None:
        if not fields:
            return
        cols = []
        vals: list[Any] = []
        for k, v in fields.items():
            if k == "summary" and v is not None and not isinstance(v, str):
                v = json.dumps(v, ensure_ascii=False)
            cols.append(f"{k} = ?")
            vals.append(v)
        vals.append(job_id)
        with self._lock, self._conn() as c:
            c.execute(f"UPDATE jobs SET {', '.join(cols)} WHERE id = ?", vals)  # noqa: S608 — 컬럼명은 내부 상수

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _row_to_dict(row) if row else None

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [_row_to_dict(r, with_summary=False) for r in rows]

    def mark_interrupted(self) -> int:
        """서버 재시작 시 실행 중이던 잡을 중단 처리 — 재제출은 무상태 검증 덕에 이어하기와 같다."""
        with self._lock, self._conn() as c:
            cur = c.execute(
                "UPDATE jobs SET status = 'interrupted', error = '서버 재시작으로 중단됨 — 재제출하면 미완료분만 처리'"
                " WHERE status IN ('queued', 'running')"
            )
            return cur.rowcount


def _row_to_dict(row: sqlite3.Row, with_summary: bool = True) -> dict[str, Any]:
    d = dict(row)
    d["inputs"] = json.loads(d["inputs"])
    d["options"] = json.loads(d["options"])
    d["flags"] = json.loads(d["flags"])
    summary = json.loads(d["summary"]) if d.get("summary") else None
    if with_summary:
        d["summary"] = summary
    else:
        # 목록은 가볍게 — 건수만
        d.pop("summary", None)
        d["summary_counts"] = (
            {k: summary.get(k) for k in ("total", "converted", "skipped", "failed", "cancelled")} if summary else None
        )
    return d
