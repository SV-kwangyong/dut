"""공용 픽스처 — 진짜 변환 도구 대신 동작을 지정할 수 있는 가짜 실행 파일(Python 스크립트)을 만든다.

가짜 도구는 `-o <dir>` 뒤 디렉터리(없으면 `-i` 파일의 디렉터리)에 `<stem>.asc`를 만든다.
behavior:
  ok            산출물 생성, exit 0
  silent_fail   산출물 없음, exit 0   (침묵 실패)
  crash         exit 3
  network       stderr에 네트워크 오류 메시지, exit 1
  hang          30초 대기
  flaky:N       N번째 호출부터 ok (호출 횟수는 카운터 파일)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path, PurePath

import pytest

_SCRIPT = r"""
import sys, time, pathlib
behavior = pathlib.Path(__file__).with_suffix(".behavior").read_text().strip()
counter = pathlib.Path(__file__).with_suffix(".count")
n = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(n))
args = sys.argv[1:]
def arg_after(flag):
    return args[args.index(flag) + 1] if flag in args else None
inp = arg_after("-i") or (args[0] if args and not args[0].startswith("-") else None)
out = arg_after("-o") or (str(pathlib.Path(inp).parent) if inp else ".")
def produce():
    stem = pathlib.Path(inp).stem if inp else "out"
    p = pathlib.Path(out) / (stem + ".asc")
    p.write_text("converted\n")
    print("Conversion complete")
if behavior.startswith("flaky:"):
    need = int(behavior.split(":")[1])
    behavior = "ok" if n >= need else "silent_fail"
if behavior == "ok":
    produce(); sys.exit(0)
if behavior == "silent_fail":
    print("Conversion complete"); sys.exit(0)
if behavior == "crash":
    print("boom", file=sys.stderr); sys.exit(3)
if behavior == "network":
    print("예기치 않은 네트워크 오류가 발생했습니다.", file=sys.stderr); sys.exit(1)
if behavior == "hang":
    time.sleep(30); sys.exit(0)
sys.exit(99)
"""


class PyScriptBackend:
    """가짜 도구(.py)를 실행하기 위한 테스트 백엔드 — argv 앞에 파이썬 인터프리터를 붙인다."""

    kind = "local"

    def wrap(self, argv: list[str]) -> list[str]:
        return [sys.executable, *argv]

    def tool_path(self, path: PurePath) -> str:
        return path.as_posix()

    def env(self) -> dict[str, str]:
        return dict(os.environ)


class FakeTool:
    def __init__(self, script: Path) -> None:
        self.script = script

    @property
    def path(self) -> str:
        return str(self.script)

    @property
    def calls(self) -> int:
        c = self.script.with_suffix(".count")
        return int(c.read_text()) if c.exists() else 0

    def set_behavior(self, behavior: str) -> None:
        self.script.with_suffix(".behavior").write_text(behavior)


@pytest.fixture
def py_backend():
    return PyScriptBackend()


@pytest.fixture
def make_fake_tool(tmp_path):
    def _make(behavior: str = "ok", name: str = "fake_tool") -> FakeTool:
        script = tmp_path / f"{name}.py"
        script.write_text(_SCRIPT, encoding="utf-8")
        tool = FakeTool(script)
        tool.set_behavior(behavior)
        return tool

    return _make
