"""런타임 조립 — 설정 + 어댑터 이름 → (어댑터 인스턴스, 백엔드, 도구 경로). CLI와 웹이 공유한다."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from misc_converter.adapters import ADAPTERS
from misc_converter.adapters.base import Adapter
from misc_converter.adapters.djlp import DjlpAdapter
from misc_converter.backends.base import Backend
from misc_converter.backends.docker import DockerBackend
from misc_converter.backends.local import LocalBackend
from misc_converter.backends.wine import WineBackend
from misc_converter.config import Config
from misc_converter.paths import PathMapper


@dataclass
class Runtime:
    adapter: Adapter
    backend: Backend
    tool_path: str


def make_adapter(name: str, cfg: Config) -> Adapter:
    cls = ADAPTERS.get(name)
    if cls is None:
        raise KeyError(f"알 수 없는 어댑터: {name} (사용 가능: {', '.join(ADAPTERS)})")
    if cls is DjlpAdapter:
        return DjlpAdapter(argv_template=cfg.djlp_argv_template)
    return cls()


def make_backend(adapter: Adapter, cfg: Config, opts: dict[str, Any]) -> Backend:
    kind = adapter.backend_kind
    if kind == "wine":
        return WineBackend(bin=cfg.wine.bin, prefix=cfg.wine.prefix, xvfb=cfg.wine.xvfb)
    if kind == "docker":
        image = cfg.tools.get(adapter.tool_key, "")
        cpus = opts.get("cpus")
        return DockerBackend(
            bin=cfg.docker.bin,
            image=image,
            volumes=list(cfg.docker.volumes),
            user=_current_uid_gid(),
            cpus=int(cpus) if cpus else None,
        )
    return LocalBackend()


def build_runtime(name: str, cfg: Config, opts: dict[str, Any]) -> Runtime:
    adapter = make_adapter(name, cfg)
    tool_path = cfg.tools.get(adapter.tool_key, "")
    if not tool_path:
        raise KeyError(f"config.tools['{adapter.tool_key}'] 가 비어 있습니다 — 도구 경로(또는 이미지)를 지정하세요")
    backend = make_backend(adapter, cfg, opts)
    if adapter.backend_kind == "wine":
        # exe 경로도 Wine 드라이브 표기로
        from pathlib import PurePosixPath

        tool_path = PathMapper.to_wine(PurePosixPath(tool_path)) if tool_path.startswith("/") else tool_path
    return Runtime(adapter=adapter, backend=backend, tool_path=tool_path)


def _current_uid_gid() -> str | None:
    # 산출물이 root 소유가 되는 것을 막는다(문서 8장 트러블슈팅). Windows(개발 환경)에는 없음.
    getuid = getattr(os, "getuid", None)
    getgid = getattr(os, "getgid", None)
    if getuid is None or getgid is None:
        return None
    return f"{getuid()}:{getgid()}"
