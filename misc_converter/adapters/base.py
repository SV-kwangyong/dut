"""어댑터 기반 클래스 — 블랙박스 변환 도구 1종을 엔진에 선언한다.

어댑터는 "무엇을 입력으로 받고, 어떤 argv로 부르고, 무엇이 생겨야 성공이며, 실패하면 무엇을 바꿔 재시도하는가"만
말한다. 실행·재시도·병렬·리포트는 엔진 몫이다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from misc_converter.backends.base import Backend
from misc_converter.engine.models import WorkItem

OptionKind = Literal["flag", "str", "int", "choice"]


@dataclass(frozen=True)
class OptionSpec:
    name: str
    kind: OptionKind
    default: Any = None
    choices: tuple[str, ...] = ()
    help: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "default": self.default,
            "choices": list(self.choices),
            "help": self.help,
        }


class Adapter(ABC):
    name: str = ""
    description: str = ""
    unit: Literal["file", "session_parent"] = "file"
    tool_key: str = ""  # config.tools 의 키
    backend_kind: Literal["local", "wine", "docker"] = "local"
    options: list[OptionSpec] = field(default_factory=list)  # type: ignore[assignment]

    # ── 스캔 ─────────────────────────────────────────────────────────
    @abstractmethod
    def match(self, path: Path) -> bool:
        """이 경로가 변환 입력 후보인가. unit=file이면 파일, session_parent면 세션 디렉터리."""

    # ── 실행 ─────────────────────────────────────────────────────────
    @abstractmethod
    def build_argv(self, item: WorkItem, opts: dict[str, Any], tool_path: str, backend: Backend) -> list[str]:
        """도구 argv(백엔드 wrap 이전)."""

    def prepare(self, item: WorkItem, opts: dict[str, Any]) -> None:
        """실행 직전 정리 작업(예: 미완성 산출물 삭제). 기본 없음."""
        return None

    def precheck(self, item: WorkItem, opts: dict[str, Any]) -> str | None:
        """선행 조건 검사. 문제 있으면 사유 문자열 → 엔진이 실행 없이 LAUNCH_ERROR 처리."""
        return None

    def retry_options(self, item: WorkItem, opts: dict[str, Any], attempt: int) -> dict[str, Any] | None:
        """재시도 시 바꿀 옵션. None이면 동일 옵션으로 재시도."""
        return None

    # ── 검증 ─────────────────────────────────────────────────────────
    @abstractmethod
    def expected_outputs(self, item: WorkItem, opts: dict[str, Any]) -> list[Path]:
        """확정적으로 알 수 있는 기대 산출물. 비어 있으면 verify가 다른 근거로 판단한다."""

    def verify(self, item: WorkItem, opts: dict[str, Any]) -> bool:
        expected = self.expected_outputs(item, opts)
        if expected:
            return all(_nonempty(p) for p in expected)
        # 확장자 미상 → 같은 stem의 신규 파일이 하나라도 생겼는가
        return any(_nonempty(p) and p != item.source for p in item.output_dir.glob(f"{item.stem}.*"))

    # ── 도우미 ─────────────────────────────────────────────────────────
    def defaults(self) -> dict[str, Any]:
        return {o.name: o.default for o in self.options}

    def merge_options(self, given: dict[str, Any]) -> dict[str, Any]:
        merged = self.defaults()
        merged.update({k: v for k, v in given.items() if v is not None})
        return merged

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "unit": self.unit,
            "backend": self.backend_kind,
            "options": [o.to_dict() for o in self.options],
        }


def _nonempty(p: Path) -> bool:
    try:
        return p.is_file() and p.stat().st_size > 0
    except OSError:
        return False
