"""misc_converter Web — FastAPI 백엔드 (storageops 패턴: 단일 index.html + REST + 폴링).

실행: uvicorn misc_converter.web.server:app --host 0.0.0.0 --port 8768
설정: 환경변수 MISC_CONVERTER_CONFIG(기본 ./config.json), MISC_CONVERTER_DB(기본 ./jobs.db)

잡 큐는 직렬(동시 1잡) — 동일 경로 동시 쓰기로 산출물이 깨지는 사고([DUT] PCAP→PCD 7장)를 큐 수준에서 막는다.
잡 내부는 엔진의 파일 단위 병렬(workers)로 처리한다.
"""

from __future__ import annotations

import os
import queue
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from misc_converter import VERSION
from misc_converter.adapters import ADAPTERS
from misc_converter.config import Config, load_config
from misc_converter.engine.models import ItemResult
from misc_converter.engine.orchestrator import run_job
from misc_converter.engine.scanner import scan
from misc_converter.paths import PathMapper
from misc_converter.runtime import build_runtime
from misc_converter.web.jobs_db import JobsDB

_INDEX = Path(__file__).parent / "index.html"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# ══════════════════════════════════════════════════════════════════════════════
# 상태 (모듈 단위 — 테스트는 create_app()으로 격리된 인스턴스를 만든다)
# ══════════════════════════════════════════════════════════════════════════════


class AppState:
    def __init__(self, cfg: Config, db: JobsDB) -> None:
        self.cfg = cfg
        self.db = db
        self.mapper = PathMapper(cfg.mounts)
        self.queue: queue.Queue[str | None] = queue.Queue()
        self.cancel_events: dict[str, threading.Event] = {}
        self.worker: threading.Thread | None = None
        self.stop = threading.Event()

    # ── 워커 ───────────────────────────────────────────────────────────
    def start_worker(self) -> None:
        self.db.mark_interrupted()
        self.worker = threading.Thread(target=self._loop, name="misc-converter-worker", daemon=True)
        self.worker.start()

    def stop_worker(self) -> None:
        self.stop.set()
        self.queue.put(None)
        if self.worker:
            self.worker.join(timeout=5)

    def _loop(self) -> None:
        while not self.stop.is_set():
            job_id = self.queue.get()
            if job_id is None:
                break
            self._execute(job_id)

    def _execute(self, job_id: str) -> None:
        job = self.db.get(job_id)
        if job is None or job["status"] != "queued":
            return
        cancel = self.cancel_events.setdefault(job_id, threading.Event())
        if cancel.is_set():
            self.db.update(job_id, status="cancelled", finished_at=_now())
            return
        self.db.update(job_id, status="running", started_at=_now())
        flags = job["flags"]

        def progress(done: int, total: int, r: ItemResult) -> None:
            self.db.update(job_id, progress_done=done, progress_total=total)

        try:
            rt = build_runtime(job["adapter"], self.cfg, rt_opts(job))
            summary = run_job(
                inputs=[str(p) for p in job["inputs"]],
                adapter=rt.adapter,
                opts=job["options"],
                backend=rt.backend,
                tool_path=rt.tool_path,
                output_dir=Path(job["output_dir"]) if job.get("output_dir") else None,
                workers=int(flags.get("workers") or self.cfg.workers),
                retries=int(flags.get("retries", self.cfg.retries)),
                timeout_s=float(flags.get("timeout_s") or self.cfg.timeout_s),
                log_dir=Path(self.cfg.log_dir),
                force=bool(flags.get("force")),
                dry_run=bool(flags.get("dry_run")),
                progress=progress,
                cancel=cancel,
            )
            status = "cancelled" if cancel.is_set() else ("failed" if summary.failed else "done")
            self.db.update(job_id, status=status, summary=summary.to_dict(), finished_at=_now())
        except Exception as ex:  # 워커는 절대 죽지 않는다 — 잡을 error로 남기고 다음 잡
            self.db.update(job_id, status="error", error=f"{type(ex).__name__}: {ex}", finished_at=_now())
        finally:
            self.cancel_events.pop(job_id, None)


def rt_opts(job: dict[str, Any]) -> dict[str, Any]:
    inst = ADAPTERS[job["adapter"]]()
    return inst.merge_options(job["options"])


# ══════════════════════════════════════════════════════════════════════════════
# 프리셋 — 사용자는 "무슨 작업"만 고른다. 어댑터·옵션은 프리셋이 채우고 고급 설정에서만 노출.
# ══════════════════════════════════════════════════════════════════════════════

PRESETS: list[dict[str, Any]] = [
    {
        "id": "dvl2asc",
        "title": "CAN 로그: .dvl → .asc",
        "desc": "Aptiv DVL을 CANalyzer용 ASC 텍스트로 변환. csv 변환·영상(DJLP) 변환의 선행 단계.",
        "adapter": "aptiv",
        "options": {"input_format": "dvl", "asc": True},
        "input_hint": "세션 폴더 또는 그 상위 폴더 (예: ...\raw\20251213). 하위의 .dvl 전부 대상, 이미 .asc가 있으면 스킵.",
    },
    {
        "id": "avi2raw",
        "title": "영상: .avi(DJLP) → .raw + timestamp.txt",
        "desc": "DJLP 코덱 영상을 raw + 프레임 타임스탬프 + SESSION_canN.txt로. 같은 이름의 .asc가 옆에 있어야 한다(dvl→asc 먼저).",
        "adapter": "djlp",
        "options": {},
        "input_hint": "세션 폴더 또는 상위 폴더. _alt.avi는 자동으로 보조 입력 처리.",
    },
    {
        "id": "txt2csv",
        "title": "CAN: SESSION_canN.txt → _ccan_3_2_1.csv / _pcan.csv",
        "desc": "csv_extractor. ccan/pcan 배정이 틀리면 자동으로 맞바꿔 재시도한다.",
        "adapter": "csv",
        "options": {},
        "input_hint": "세션 폴더들의 상위 폴더 (예: .../FV/DRV). 각 세션 폴더에 _canN.txt와 SESSION.txt 필요.",
    },
    {
        "id": "pcap2pcd",
        "title": "라이다: .pcap → PCD tar",
        "desc": "surf_pcap2pcd_converter(Docker). convert_log.json의 success로 판정, 미완성 tar는 자동 정리.",
        "adapter": "pcap2pcd",
        "options": {},
        "input_hint": "pcap 파일 또는 폴더. tar는 pcap 옆에 생성.",
    },
    {
        "id": "aptiv_custom",
        "title": "Aptiv 변환기 — 다른 포맷 조합 (고급)",
        "desc": "dvl/dvs/mudp/asc/mf4 → asc/dvl/dvs/lcm/mudp/pcap/adtf 중 원하는 조합. 고급 설정에서 출력 포맷을 직접 체크.",
        "adapter": "aptiv",
        "options": {"input_format": "any"},
        "input_hint": "입력 포맷 필터와 출력 포맷을 고급 설정에서 지정.",
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# 요청 모델
# ══════════════════════════════════════════════════════════════════════════════


class JobRequest(BaseModel):
    adapter: str
    inputs: list[str] = Field(min_length=1)
    options: dict[str, Any] = Field(default_factory=dict)
    output_dir: str | None = None
    workers: int | None = None
    retries: int | None = None
    timeout_s: int | None = None
    force: bool = False
    dry_run: bool = False


# ══════════════════════════════════════════════════════════════════════════════
# 앱 팩토리
# ══════════════════════════════════════════════════════════════════════════════


def create_app(cfg: Config | None = None, db_path: str | Path | None = None) -> FastAPI:
    if cfg is None:
        cfg = load_config(os.environ.get("MISC_CONVERTER_CONFIG", "config.json"))
    db = JobsDB(db_path or os.environ.get("MISC_CONVERTER_DB", "jobs.db"))
    state = AppState(cfg, db)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        state.start_worker()
        try:
            yield
        finally:
            state.stop_worker()

    app = FastAPI(title="misc_converter", version=VERSION, lifespan=lifespan)
    app.state.mc = state

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(_INDEX, media_type="text/html")

    @app.get("/api/meta")
    def meta() -> dict[str, Any]:
        return {"version": VERSION, "mounts": [str(r) for r in state.mapper.roots()], "log_dir": cfg.log_dir}

    @app.get("/api/adapters")
    def adapters() -> list[dict[str, Any]]:
        return [cls().describe() for cls in ADAPTERS.values()]

    @app.get("/api/presets")
    def presets() -> list[dict[str, Any]]:
        return PRESETS

    @app.post("/api/preview")
    def preview(req: JobRequest) -> dict[str, Any]:
        """실행 없이 스캔만 — 변환 예정/스킵 건수와 앞부분 목록. 사용자가 실행 전 범위를 확인하는 용도."""
        if req.adapter not in ADAPTERS:
            raise HTTPException(400, f"알 수 없는 어댑터: {req.adapter}")
        try:
            inputs: list[str | Path] = [str(state.mapper.to_local(p)) for p in req.inputs]
            output_dir = Path(str(state.mapper.to_local(req.output_dir))) if req.output_dir else None
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        inst = ADAPTERS[req.adapter]()
        opts = inst.merge_options(req.options)
        try:
            entries = scan(inputs, inst, opts, output_dir=output_dir, force=req.force)
        except FileNotFoundError as e:
            raise HTTPException(404, str(e)) from e
        todo = [e for e in entries if not e.skip]
        skipped = [e for e in entries if e.skip]
        return {
            "total": len(entries),
            "todo": len(todo),
            "skipped": len(skipped),
            "sample_todo": [str(e.item.source) for e in todo[:20]],
            "sample_skipped": [str(e.item.source) for e in skipped[:10]],
        }

    @app.get("/api/browse")
    def browse(path: str) -> dict[str, Any]:
        try:
            local = state.mapper.to_local(path)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        p = Path(local)
        if not p.is_dir():
            raise HTTPException(404, f"디렉터리가 아니거나 없습니다: {local}")
        dirs: list[str] = []
        files: list[str] = []
        try:
            for child in sorted(p.iterdir(), key=lambda c: c.name.lower()):
                (dirs if child.is_dir() else files).append(child.name)
        except OSError as e:
            raise HTTPException(500, f"읽기 실패: {e}") from e
        return {"path": str(local), "dirs": dirs, "files": files[:500]}

    @app.post("/api/jobs", status_code=202)
    def submit(req: JobRequest) -> dict[str, Any]:
        if req.adapter not in ADAPTERS:
            raise HTTPException(400, f"알 수 없는 어댑터: {req.adapter}")
        try:
            inputs = [str(state.mapper.to_local(p)) for p in req.inputs]
            output_dir = str(state.mapper.to_local(req.output_dir)) if req.output_dir else None
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        try:
            build_runtime(req.adapter, cfg, rt_opts({"adapter": req.adapter, "options": req.options}))
        except KeyError as e:
            raise HTTPException(400, str(e)) from e
        job_id = uuid4().hex[:12]
        job = {
            "id": job_id,
            "adapter": req.adapter,
            "inputs": inputs,
            "options": req.options,
            "output_dir": output_dir,
            "flags": {
                "workers": req.workers,
                "retries": req.retries if req.retries is not None else cfg.retries,
                "timeout_s": req.timeout_s,
                "force": req.force,
                "dry_run": req.dry_run,
            },
            "status": "queued",
            "created_at": _now(),
        }
        db.insert(job)
        state.cancel_events[job_id] = threading.Event()
        state.queue.put(job_id)
        return {"id": job_id, "status": "queued"}

    @app.get("/api/jobs")
    def list_jobs(limit: int = 100) -> list[dict[str, Any]]:
        return db.list(limit=limit)

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        job = db.get(job_id)
        if job is None:
            raise HTTPException(404, "잡이 없습니다")
        return job

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict[str, Any]:
        job = db.get(job_id)
        if job is None:
            raise HTTPException(404, "잡이 없습니다")
        if job["status"] not in ("queued", "running"):
            return {"id": job_id, "status": job["status"]}
        ev = state.cancel_events.setdefault(job_id, threading.Event())
        ev.set()
        if job["status"] == "queued":
            db.update(job_id, status="cancelled", finished_at=_now())
            return {"id": job_id, "status": "cancelled"}
        return {"id": job_id, "status": "cancelling"}

    return app


def _default_app() -> FastAPI:
    # uvicorn misc_converter.web.server:app — 설정 파일이 없으면 시작 시점에 명확히 실패한다
    return create_app()


try:
    app = _default_app()
except FileNotFoundError:
    # 테스트·문서 빌드 등 설정 없는 import를 허용. 운영은 MISC_CONVERTER_CONFIG 필수.
    app = FastAPI(title="misc_converter (설정 없음)")

    @app.get("/")
    def _no_config() -> dict[str, str]:
        return {"error": "config.json 이 없습니다. MISC_CONVERTER_CONFIG 환경변수 또는 ./config.json 을 준비하세요."}


__all__ = ["app", "create_app", "PurePosixPath"]
