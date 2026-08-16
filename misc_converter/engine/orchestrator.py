"""오케스트레이터 — 스캔 → (병렬) 실행 → 리포트. CLI와 웹이 공유하는 유일한 진입점."""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from misc_converter.adapters.base import Adapter
from misc_converter.backends.base import Backend
from misc_converter.engine import report
from misc_converter.engine.models import ItemResult, ItemStatus, RunSummary
from misc_converter.engine.runner import DEFAULT_BACKOFF, run_item
from misc_converter.engine.scanner import scan

ProgressCallback = Callable[[int, int, ItemResult], None]  # (완료 수, 전체 수, 방금 끝난 결과)


def run_job(
    inputs: list[str | Path],
    adapter: Adapter,
    opts: dict[str, Any],
    backend: Backend,
    tool_path: str,
    output_dir: Path | None = None,
    workers: int = 4,
    retries: int = 2,
    timeout_s: float = 1800,
    log_dir: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
    backoff: tuple[float, ...] = DEFAULT_BACKOFF,
) -> RunSummary:
    started_at = report.now_iso()
    full_opts = adapter.merge_options(opts)
    entries = scan(inputs, adapter, full_opts, output_dir=output_dir, force=force)
    total = len(entries)
    results: list[ItemResult] = []
    done = 0

    def emit(r: ItemResult) -> None:
        nonlocal done
        done += 1
        if progress:
            progress(done, total, r)

    todo = []
    for e in entries:
        if e.skip:
            r = ItemResult(item=e.item, status=ItemStatus.SKIPPED, message="기대 산출물 존재")
            results.append(r)
            emit(r)
        elif dry_run:
            r = ItemResult(item=e.item, status=ItemStatus.PLANNED)
            try:
                r.argv = backend.wrap(adapter.build_argv(e.item, full_opts, tool_path, backend))
            except ValueError as ex:
                r.status = ItemStatus.FAILED
                r.message = str(ex)
            results.append(r)
            emit(r)
        else:
            todo.append(e.item)

    if todo:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {}
            for item in todo:
                if cancel is not None and cancel.is_set():
                    r = ItemResult(item=item, status=ItemStatus.CANCELLED)
                    results.append(r)
                    emit(r)
                    continue
                futures[
                    pool.submit(
                        _run_guarded, item, adapter, full_opts, backend, tool_path, retries, timeout_s, backoff, cancel
                    )
                ] = item
            for fut in as_completed(futures):
                r = fut.result()
                results.append(r)
                emit(r)

    # 리포트는 스캔 순서로 정렬(병렬 완료 순서 무관)
    order = {id(e.item): i for i, e in enumerate(entries)}
    results.sort(key=lambda r: order.get(id(r.item), 1 << 30))

    summary = RunSummary(
        adapter=adapter.name,
        options=full_opts,
        results=results,
        started_at=started_at,
        finished_at=report.now_iso(),
    )
    if log_dir is not None:
        report.write(summary, log_dir)
    return summary


def _run_guarded(
    item: Any,
    adapter: Adapter,
    opts: dict[str, Any],
    backend: Backend,
    tool_path: str,
    retries: int,
    timeout_s: float,
    backoff: tuple[float, ...],
    cancel: threading.Event | None,
) -> ItemResult:
    if cancel is not None and cancel.is_set():
        return ItemResult(item=item, status=ItemStatus.CANCELLED)
    try:
        return run_item(item, adapter, opts, backend, tool_path, retries=retries, timeout_s=timeout_s, backoff=backoff)
    except Exception as ex:  # 워커 스레드 예외가 잡 전체를 죽이지 않도록
        r = ItemResult(item=item, status=ItemStatus.FAILED, attempts=1)
        r.message = f"내부 오류: {type(ex).__name__}: {ex}"
        return r
