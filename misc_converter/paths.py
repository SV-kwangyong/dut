"""경로 매퍼 — 같은 Qumulo 데이터를 가리키는 UNC(Windows)·Linux 마운트·Wine 드라이브 경로를 상호 변환한다.

웹 사용자는 Windows 탐색기에서 복사한 UNC 경로를 그대로 붙여 넣고, 서버(Linux)는 마운트 경로로,
Wine 백엔드는 Z: 드라이브 경로로 도구에 전달한다. 등록된 마운트 밖의 경로는 거부한다(외부 입력 검증, 헌법 §XIII).
"""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath

from misc_converter.config import Mount


class PathMapper:
    def __init__(self, mounts: dict[str, Mount]) -> None:
        self._mounts = mounts

    def to_local(self, raw: str) -> PurePosixPath:
        """UNC·Windows·Linux 표기의 입력 경로를 서버 로컬(Linux 마운트) 경로로 변환한다."""
        text = raw.strip()
        if text.startswith(("\\\\", "//")):
            return self._unc_to_local(text)
        candidate = PurePosixPath(text.replace("\\", "/"))
        if self.is_allowed(candidate):
            return candidate
        raise ValueError(f"등록된 마운트 밖의 경로입니다: {raw}")

    def _unc_to_local(self, text: str) -> PurePosixPath:
        win = PureWindowsPath(text.replace("/", "\\"))
        parts = [p for p in win.parts]
        for mount in self._mounts.values():
            root = PureWindowsPath(mount.windows)
            root_parts = list(root.parts)
            if [p.lower() for p in parts[: len(root_parts)]] == [p.lower() for p in root_parts]:
                rest = parts[len(root_parts) :]
                return PurePosixPath(mount.linux, *rest)
        raise ValueError(f"등록된 마운트 밖의 UNC 경로입니다: {text}")

    def is_allowed(self, path: PurePosixPath) -> bool:
        if ".." in path.parts:
            return False
        return any(self._under(path, PurePosixPath(m.linux)) for m in self._mounts.values())

    @staticmethod
    def _under(path: PurePosixPath, root: PurePosixPath) -> bool:
        return path == root or root in path.parents

    @staticmethod
    def to_wine(path: PurePosixPath) -> str:
        """Linux 절대 경로 → Wine 기본 드라이브 매핑(Z: = /) 경로."""
        return "Z:" + str(path).replace("/", "\\")

    def roots(self) -> list[PurePosixPath]:
        return [PurePosixPath(m.linux) for m in self._mounts.values()]
