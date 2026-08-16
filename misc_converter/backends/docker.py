"""Docker 백엔드 — 컨테이너 이미지로 배포되는 변환기(pcap2pcd) 실행."""

from __future__ import annotations

from pathlib import PurePath

from misc_converter.backends.base import base_env


class DockerBackend:
    kind = "docker"
    use_pty = False

    def __init__(
        self,
        bin: str,
        image: str,
        volumes: list[str],
        user: str | None = None,
        cpus: int | None = None,
    ) -> None:
        self._bin = bin
        self._image = image
        self._volumes = volumes
        self._user = user
        self._cpus = cpus

    def wrap(self, argv: list[str]) -> list[str]:
        cmd = [self._bin, "run", "--rm"]
        if self._user:
            cmd += ["--user", self._user]
        if self._cpus:
            cmd += ["--cpus", str(self._cpus)]
        for v in self._volumes:
            cmd += ["-v", v]
        cmd.append(self._image)
        return cmd + list(argv)

    def tool_path(self, path: PurePath) -> str:
        # 볼륨을 동일 경로로 마운트하는 것이 전제(config docker.volumes: "/mnt/qumulo:/mnt/qumulo")
        return path.as_posix()

    def env(self) -> dict[str, str]:
        return base_env()
