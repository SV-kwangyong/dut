"""실행 백엔드 프로토콜 — 도구 argv를 실제 실행 환경(local/wine/docker)에 맞게 감싼다."""

from __future__ import annotations

import os
from pathlib import PurePath
from typing import Protocol


class Backend(Protocol):
    kind: str
    # True면 엔진이 도구를 pseudo-terminal 아래에서 실행한다.
    # AptivFileConversion은 진행률 표시에 Console.CursorLeft를 쓰는데 stdout이 파이프면 "Invalid handle"로 죽는다
    # (Wine 스파이크 2026-08-16 실측 — Windows에서도 동일).
    use_pty: bool

    def wrap(self, argv: list[str]) -> list[str]:
        """도구 argv → 최종 subprocess argv."""
        ...

    def tool_path(self, path: PurePath) -> str:
        """서버 로컬 경로 → 도구가 이해하는 경로 문자열."""
        ...

    def env(self) -> dict[str, str]: ...


def base_env() -> dict[str, str]:
    return dict(os.environ)
