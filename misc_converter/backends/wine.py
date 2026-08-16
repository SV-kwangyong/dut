"""Wine 백엔드 — Windows exe를 우분투에서 실행. GUI 프레임워크(WinForms/Qt) 초기화용 xvfb 선택."""

from __future__ import annotations

from pathlib import PurePath, PurePosixPath

from misc_converter.backends.base import base_env
from misc_converter.paths import PathMapper


class WineBackend:
    kind = "wine"
    use_pty = True

    def __init__(self, bin: str = "wine", prefix: str = "", xvfb: bool = True) -> None:
        self._bin = bin
        self._prefix = prefix
        self._xvfb = xvfb

    def wrap(self, argv: list[str]) -> list[str]:
        head = ["xvfb-run", "-a"] if self._xvfb else []
        return [*head, self._bin, *argv]

    def tool_path(self, path: PurePath) -> str:
        return PathMapper.to_wine(PurePosixPath(path.as_posix()))

    def env(self) -> dict[str, str]:
        e = base_env()
        # WINEDEBUG=-all: fixme 로그가 stderr를 채워 실패 분류를 방해하는 것을 막는다
        e["WINEDEBUG"] = "-all"
        if self._prefix:
            e["WINEPREFIX"] = self._prefix
        return e
