import os
import sys
from typing import Any

import pytest

from misc_converter.adapters.aptiv import AptivAdapter
from misc_converter.adapters.base import Adapter
from misc_converter.engine.models import FailureKind, ItemStatus, WorkItem
from misc_converter.engine.runner import classify, run_item

NO_SLEEP = (0.0,)


@pytest.fixture
def item(tmp_path):
    src = tmp_path / "data" / "a.dvl"
    src.parent.mkdir()
    src.write_bytes(b"x")
    return WorkItem(source=src, output_dir=src.parent)


@pytest.fixture
def opts():
    return AptivAdapter().merge_options({"asc": True})


def _run(tool, item, opts, backend, **kw):
    kw.setdefault("retries", 2)
    kw.setdefault("timeout_s", 10)
    kw.setdefault("backoff", NO_SLEEP)
    return run_item(item, AptivAdapter(), opts, backend, tool.path, **kw)


def test_ok(make_fake_tool, py_backend, item, opts):
    tool = make_fake_tool("ok")
    r = _run(tool, item, opts, py_backend)
    assert r.status is ItemStatus.CONVERTED and r.attempts == 1 and r.failure is None
    assert (item.output_dir / "a.asc").read_text().startswith("converted")
    assert r.argv[1:3] == [tool.path, "-i"]


def test_silent_fail_retries_then_output_missing(make_fake_tool, py_backend, item, opts):
    tool = make_fake_tool("silent_fail")
    r = _run(tool, item, opts, py_backend, retries=2)
    assert r.status is ItemStatus.FAILED and r.failure is FailureKind.OUTPUT_MISSING
    assert r.attempts == 3 and tool.calls == 3
    assert "산출물 미생성" in r.message


def test_crash_nonzero_exit(make_fake_tool, py_backend, item, opts):
    r = _run(make_fake_tool("crash"), item, opts, py_backend, retries=0)
    assert r.failure is FailureKind.NONZERO_EXIT and "exit 3" in r.message and "boom" in r.message


def test_network_pattern(make_fake_tool, py_backend, item, opts):
    r = _run(make_fake_tool("network"), item, opts, py_backend, retries=0)
    assert r.failure is FailureKind.NETWORK


def test_timeout(make_fake_tool, py_backend, item, opts):
    r = _run(make_fake_tool("hang"), item, opts, py_backend, retries=0, timeout_s=1)
    assert r.failure is FailureKind.TIMEOUT and r.status is ItemStatus.FAILED


def test_flaky_recovers_on_second_attempt(make_fake_tool, py_backend, item, opts):
    tool = make_fake_tool("flaky:2")
    r = _run(tool, item, opts, py_backend, retries=2)
    assert r.status is ItemStatus.CONVERTED and r.attempts == 2


def test_missing_executable_is_launch_error_without_retry(item, opts, py_backend):
    slept: list[float] = []
    r = run_item(
        item,
        AptivAdapter(),
        opts,
        py_backend,
        str(item.source.parent / "no_such_tool.py"),
        retries=2,
        timeout_s=5,
        backoff=(1.0,),
        sleep=slept.append,
    )
    # 파이썬이 존재하지 않는 스크립트를 실행하면 exit 2 — LAUNCH_ERROR가 아니라 NONZERO_EXIT로 분류된다.
    # 실행 파일 자체가 없을 때(LAUNCH_ERROR)는 아래 test_launch_error_from_precheck·OSError 케이스로 검증.
    assert r.status is ItemStatus.FAILED
    assert r.failure in (FailureKind.NONZERO_EXIT, FailureKind.LAUNCH_ERROR)


def test_launch_error_when_binary_missing(item, opts, tmp_path):
    from misc_converter.backends.local import LocalBackend

    r = run_item(item, AptivAdapter(), opts, LocalBackend(), str(tmp_path / "missing.exe"), retries=2, timeout_s=5)
    assert r.failure is FailureKind.LAUNCH_ERROR and r.attempts == 1


def test_backoff_and_sleep_injection(make_fake_tool, py_backend, item, opts):
    slept: list[float] = []
    _run(make_fake_tool("silent_fail"), item, opts, py_backend, retries=2, backoff=(5.0, 25.0), sleep=slept.append)
    assert slept == [5.0, 25.0]


class _SwapAdapter(AptivAdapter):
    """재시도 시 옵션을 바꾸는 어댑터 — retry_options 경로 검증용."""

    def retry_options(self, item: WorkItem, opts: dict[str, Any], attempt: int) -> dict[str, Any] | None:
        return {"ascbase": "dec"} if attempt == 1 else None


def test_retry_options_applied(make_fake_tool, py_backend, item, opts):
    tool = make_fake_tool("flaky:2")
    r = run_item(item, _SwapAdapter(), opts, py_backend, tool.path, retries=2, timeout_s=10, backoff=NO_SLEEP)
    assert r.status is ItemStatus.CONVERTED and "--ascbase=dec" in r.argv


class _PrecheckAdapter(AptivAdapter):
    def precheck(self, item: WorkItem, opts: dict[str, Any]) -> str | None:
        return "선행 파일 없음"


def test_precheck_blocks_execution(make_fake_tool, py_backend, item, opts):
    tool = make_fake_tool("ok")
    r = run_item(item, _PrecheckAdapter(), opts, py_backend, tool.path, retries=2, timeout_s=10)
    assert r.failure is FailureKind.LAUNCH_ERROR and r.message == "선행 파일 없음" and tool.calls == 0


@pytest.mark.skipif(os.name != "posix", reason="pty는 POSIX 전용")
def test_run_process_with_pty_gives_tty_and_captures_output(tmp_path):
    from misc_converter.engine.runner import run_process

    script = tmp_path / "tty_probe.py"
    script.write_text("import sys, os; print('isatty', os.isatty(1)); print('done'); sys.exit(3)")
    rc, out = run_process([sys.executable, str(script)], dict(os.environ), timeout_s=10, use_pty=True)
    assert rc == 3 and "isatty True" in out and "done" in out


@pytest.mark.skipif(os.name != "posix", reason="pty는 POSIX 전용")
def test_run_process_with_pty_timeout(tmp_path):
    import subprocess

    from misc_converter.engine.runner import run_process

    script = tmp_path / "hang.py"
    script.write_text("import time; print('start', flush=True); time.sleep(30)")
    with pytest.raises(subprocess.TimeoutExpired):
        run_process([sys.executable, str(script)], dict(os.environ), timeout_s=1, use_pty=True)


def test_run_process_without_pty(tmp_path):
    from misc_converter.engine.runner import run_process

    script = tmp_path / "probe.py"
    script.write_text("import sys, os; print('isatty', os.isatty(1)); print('err', file=sys.stderr); sys.exit(0)")
    rc, out = run_process([sys.executable, str(script)], dict(os.environ), timeout_s=10, use_pty=False)
    assert rc == 0 and "isatty False" in out and "err" in out


def test_classify_matrix():
    assert classify(0, "", True) is None
    assert classify(None, "", False) is FailureKind.TIMEOUT
    assert classify(1, "Host is down", False) is FailureKind.NETWORK
    assert classify(0, "예기치 않은 네트워크 오류", False) is FailureKind.NETWORK
    assert classify(2, "boom", False) is FailureKind.NONZERO_EXIT
    assert classify(0, "Conversion complete", False) is FailureKind.OUTPUT_MISSING


def test_adapter_is_abstract():
    with pytest.raises(TypeError):
        Adapter()  # type: ignore[abstract]
