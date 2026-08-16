"""리포트 — 실행별 텍스트 로그(UTF-8·한국어)와 JSON 요약을 남긴다. 래퍼 로그가 단일 진실 소스다."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from misc_converter.engine.models import ItemStatus, RunSummary


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def run_stamp(started_at: str) -> str:
    return datetime.fromisoformat(started_at).strftime("%Y%m%d_%H%M%S")


def format_summary(summary: RunSummary) -> str:
    lines = [
        f"[misc_converter] 어댑터={summary.adapter}  시작={summary.started_at}  종료={summary.finished_at}",
        f"전체 {summary.total} / 변환 {summary.converted} / 스킵 {summary.skipped} / 실패 {summary.failed}"
        + (f" / 계획 {summary.count(ItemStatus.PLANNED)}" if summary.count(ItemStatus.PLANNED) else "")
        + (f" / 취소 {summary.count(ItemStatus.CANCELLED)}" if summary.count(ItemStatus.CANCELLED) else ""),
    ]
    failed = [r for r in summary.results if r.status is ItemStatus.FAILED]
    if failed:
        lines.append("실패 목록:")
        for r in failed:
            kind = r.failure.value if r.failure else "-"
            first = r.message.splitlines()[0] if r.message else ""
            lines.append(f"  - {r.item.source}  [{kind}, {r.attempts}회]  {first}")
    return "\n".join(lines)


def write(summary: RunSummary, log_dir: Path) -> RunSummary:
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = run_stamp(summary.started_at)
    log_path = log_dir / f"convert_{stamp}.log"
    json_path = log_dir / f"convert_{stamp}.json"
    # 같은 초에 두 실행이 겹치면 접미사
    n = 1
    while log_path.exists() or json_path.exists():
        n += 1
        log_path = log_dir / f"convert_{stamp}_{n}.log"
        json_path = log_dir / f"convert_{stamp}_{n}.json"
    summary.log_path = log_path
    summary.json_path = json_path

    with log_path.open("w", encoding="utf-8") as fh:
        fh.write(format_summary(summary) + "\n\n")
        fh.write(f"옵션: {json.dumps(summary.options, ensure_ascii=False)}\n\n")
        for r in summary.results:
            fh.write(f"[{r.status.value}] {r.item.source}\n")
            if r.argv:
                fh.write(f"  argv: {' '.join(r.argv)}\n")
            if r.attempts:
                fh.write(f"  시도: {r.attempts}  소요: {r.duration_s:.1f}s\n")
            if r.message:
                for ln in r.message.splitlines():
                    fh.write(f"  | {ln}\n")
    json_path.write_text(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
