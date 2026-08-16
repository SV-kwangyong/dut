"""항목 실행기 — 작업 1건을 실행하고 산출물로 성패를 판정하며, 실패 유형에 따라 재시도한다.

exit code는 참고 정보일 뿐 판정 근거가 아니다(WinForms exe는 실패해도 0, csv_extractor는 침묵 실패).
"""

from __future__ import annotations

import re
import subprocess
import time
from collections.abc import Callable
from typing import Any

from misc_converter.adapters.base import Adapter
from misc_converter.backends.base import Backend
from misc_converter.engine.models import FailureKind, ItemResult, ItemStatus, WorkItem

# 네트워크/스토리지 계층 오류로 판단하는 stdout/stderr 패턴 — 재시도 가치가 높다
NETWORK_PATTERNS = re.compile(
    r"네트워크|network|Host is down|STATUS_|I/O error|Input/output error|핸들이 잘못|"
    r"지정된 네트워크 이름을 더 이상 사용할 수 없|Transport endpoint|Stale file handle",
    re.IGNORECASE,
)

DEFAULT_BACKOFF: tuple[float, ...] = (5.0, 25.0)


def classify(returncode: int | None, output: str, verified: bool) -> FailureKind | None:
    if verified:
        return None
    if returncode is None:
        return FailureKind.TIMEOUT
    if NETWORK_PATTERNS.search(output):
        return FailureKind.NETWORK
    if returncode != 0:
        return FailureKind.NONZERO_EXIT
    return FailureKind.OUTPUT_MISSING


def _tail(text: str, n: int = 8) -> str:
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    return "\n".join(lines[-n:])


def run_item(
    item: WorkItem,
    adapter: Adapter,
    opts: dict[str, Any],
    backend: Backend,
    tool_path: str,
    retries: int = 2,
    timeout_s: float = 1800,
    backoff: tuple[float, ...] = DEFAULT_BACKOFF,
    sleep: Callable[[float], None] = time.sleep,
) -> ItemResult:
    started = time.monotonic()
    result = ItemResult(item=item, status=ItemStatus.FAILED)

    reason = adapter.precheck(item, opts)
    if reason:
        result.failure = FailureKind.LAUNCH_ERROR
        result.message = reason
        result.duration_s = time.monotonic() - started
        return result

    current_opts = dict(opts)
    for attempt in range(1, retries + 2):
        result.attempts = attempt
        argv = adapter.build_argv(item, current_opts, tool_path, backend)
        result.argv = backend.wrap(argv)
        adapter.prepare(item, current_opts)
        try:
            proc = subprocess.run(
                result.argv,
                capture_output=True,
                timeout=timeout_s,
                env=backend.env(),
            )
            returncode: int | None = proc.returncode
            output = _decode(proc.stdout) + "\n" + _decode(proc.stderr)
        except subprocess.TimeoutExpired as e:
            returncode = None
            output = _decode(e.stdout) + "\n" + _decode(e.stderr)
        except (FileNotFoundError, PermissionError, OSError) as e:
            result.failure = FailureKind.LAUNCH_ERROR
            result.message = f"실행 실패: {e}"
            break

        verified = adapter.verify(item, current_opts)
        failure = classify(returncode, output, verified)
        if failure is None:
            result.status = ItemStatus.CONVERTED
            result.failure = None
            result.message = ""
            break

        result.failure = failure
        result.message = _describe(failure, returncode, output)
        if attempt > retries:
            break
        changed = adapter.retry_options(item, current_opts, attempt)
        if changed is not None:
            current_opts = {**current_opts, **changed}
        wait = backoff[min(attempt - 1, len(backoff) - 1)] if backoff else 0.0
        if wait > 0:
            sleep(wait)

    result.duration_s = time.monotonic() - started
    return result


def _decode(data: bytes | str | None) -> str:
    """도구 출력 디코딩 — UTF-8 우선, 실패 시 cp949(한국어 Windows/Wine 로케일), 최후엔 치환."""
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    for enc in ("utf-8", "cp949"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _describe(kind: FailureKind, returncode: int | None, output: str) -> str:
    label = {
        FailureKind.OUTPUT_MISSING: "산출물 미생성",
        FailureKind.NONZERO_EXIT: f"비정상 종료(exit {returncode})",
        FailureKind.NETWORK: "네트워크/스토리지 오류",
        FailureKind.TIMEOUT: "타임아웃",
        FailureKind.LAUNCH_ERROR: "실행 불가",
    }[kind]
    tail = _tail(output)
    return f"{label}\n{tail}" if tail else label
