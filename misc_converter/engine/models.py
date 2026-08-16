"""엔진 공용 데이터 모델."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class FailureKind(str, Enum):
    OUTPUT_MISSING = "output_missing"  # 프로세스는 끝났으나 기대 산출물 없음(침묵 실패 포함)
    NONZERO_EXIT = "nonzero_exit"
    NETWORK = "network"  # SMB/NFS 등 네트워크 오류 패턴 감지
    TIMEOUT = "timeout"
    LAUNCH_ERROR = "launch_error"  # 실행 파일 없음·선행 조건 미충족 — 재시도 무의미


class ItemStatus(str, Enum):
    CONVERTED = "converted"
    SKIPPED = "skipped"
    FAILED = "failed"
    PLANNED = "planned"  # dry-run
    CANCELLED = "cancelled"


@dataclass
class WorkItem:
    """변환 작업 단위. 어댑터의 unit에 따라 파일 1개 또는 세션 상위 디렉터리 1개."""

    source: Path
    output_dir: Path
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def stem(self) -> str:
        return self.source.stem


@dataclass
class ItemResult:
    item: WorkItem
    status: ItemStatus
    attempts: int = 0
    failure: FailureKind | None = None
    message: str = ""
    duration_s: float = 0.0
    argv: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": str(self.item.source),
            "output_dir": str(self.item.output_dir),
            "status": self.status.value,
            "attempts": self.attempts,
            "failure": self.failure.value if self.failure else None,
            "message": self.message,
            "duration_s": round(self.duration_s, 3),
            "argv": self.argv,
        }


@dataclass
class RunSummary:
    adapter: str
    options: dict[str, Any]
    results: list[ItemResult]
    started_at: str
    finished_at: str
    log_path: Path | None = None
    json_path: Path | None = None

    def count(self, status: ItemStatus) -> int:
        return sum(1 for r in self.results if r.status is status)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def converted(self) -> int:
        return self.count(ItemStatus.CONVERTED)

    @property
    def skipped(self) -> int:
        return self.count(ItemStatus.SKIPPED)

    @property
    def failed(self) -> int:
        return self.count(ItemStatus.FAILED)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "adapter": self.adapter,
            "options": self.options,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total": self.total,
            "converted": self.converted,
            "skipped": self.skipped,
            "failed": self.failed,
            "planned": self.count(ItemStatus.PLANNED),
            "cancelled": self.count(ItemStatus.CANCELLED),
            "log_path": str(self.log_path) if self.log_path else None,
            "json_path": str(self.json_path) if self.json_path else None,
            "results": [r.to_dict() for r in self.results],
        }
        return d


__all__ = ["FailureKind", "ItemStatus", "WorkItem", "ItemResult", "RunSummary", "asdict"]
