from __future__ import annotations

from pathlib import PurePath

from misc_converter.backends.base import base_env


class LocalBackend:
    kind = "local"
    use_pty = False

    def wrap(self, argv: list[str]) -> list[str]:
        return list(argv)

    def tool_path(self, path: PurePath) -> str:
        return path.as_posix()

    def env(self) -> dict[str, str]:
        return base_env()
