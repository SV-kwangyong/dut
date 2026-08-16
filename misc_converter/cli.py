"""CLI — 엔진 위 얇은 껍데기. 어댑터별 서브커맨드는 OptionSpec에서 자동 생성한다.

  misc-converter adapters
  misc-converter aptiv -i /mnt/qumulo/.../raw --asc [--dry-run] [--force]
  misc-converter csv   -i /mnt/qumulo/.../DRV --ccan can2 --pcan can1
종료 코드: 0=전부 성공(스킵 포함) / 1=실패 존재 / 2=인자·설정 오류
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from misc_converter import VERSION
from misc_converter.adapters import ADAPTERS
from misc_converter.adapters.base import Adapter, OptionSpec
from misc_converter.config import Config, load_config
from misc_converter.engine.models import ItemResult, ItemStatus
from misc_converter.engine.orchestrator import run_job
from misc_converter.engine.report import format_summary
from misc_converter.runtime import build_runtime

DEFAULT_CONFIG = Path("config.json")


def _add_option(parser: argparse.ArgumentParser, spec: OptionSpec) -> None:
    flag = f"--{spec.name.replace('_', '-')}"
    kw: dict[str, Any] = {"dest": spec.name, "help": spec.help}
    if spec.kind == "flag":
        if spec.default:
            # 기본 True인 플래그는 --no-x 로 끈다
            parser.add_argument(
                f"--no-{spec.name.replace('_', '-')}", dest=spec.name, action="store_false", help=spec.help
            )
            parser.set_defaults(**{spec.name: None})
        else:
            parser.add_argument(flag, action="store_true", default=None, **kw)
        return
    if spec.kind == "int":
        kw["type"] = int
    if spec.kind == "choice":
        kw["choices"] = list(spec.choices)
    parser.add_argument(flag, default=None, **kw)


def build_parser(adapters: dict[str, type[Adapter]] | None = None) -> argparse.ArgumentParser:
    adapters = adapters or ADAPTERS
    p = argparse.ArgumentParser(prog="misc-converter", description="기타 인바운드 포맷 변환 오케스트레이터")
    p.add_argument("--version", action="version", version=f"misc-converter {VERSION}")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="config.json 경로")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("adapters", help="사용 가능한 어댑터 목록")
    for name, cls in adapters.items():
        inst = cls()
        sp = sub.add_parser(name, help=inst.description)
        sp.add_argument("-i", "--input", dest="inputs", nargs="+", required=True, help="입력 파일/디렉터리/와일드카드")
        sp.add_argument("-o", "--output-dir", type=Path, default=None, help="출력 디렉터리(기본: 원본 옆)")
        sp.add_argument("--workers", type=int, default=None)
        sp.add_argument("--retries", type=int, default=None)
        sp.add_argument("--timeout", type=int, default=None, help="파일당 타임아웃(초)")
        sp.add_argument("--force", action="store_true", help="기존 산출물 무시하고 재변환")
        sp.add_argument("--dry-run", action="store_true", help="실행 없이 계획만 출력")
        sp.add_argument("--log-dir", type=Path, default=None)
        for spec in inst.options:
            _add_option(sp, spec)
    return p


def _progress_printer(done: int, total: int, r: ItemResult) -> None:
    mark = {
        ItemStatus.CONVERTED: "OK ",
        ItemStatus.SKIPPED: "SKP",
        ItemStatus.FAILED: "ERR",
        ItemStatus.PLANNED: "PLN",
        ItemStatus.CANCELLED: "CXL",
    }[r.status]
    line = f"[{done}/{total}] {mark} {r.item.source}"
    if r.status is ItemStatus.FAILED and r.message:
        line += f"  — {r.message.splitlines()[0]}"
    print(line, flush=True)


def _force_utf8_stdio() -> None:
    """Windows 콘솔(cp949)에서 한국어·특수문자 출력이 UnicodeEncodeError로 죽지 않도록."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: Sequence[str] | None = None) -> int:
    _force_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "adapters":
        for name, cls in ADAPTERS.items():
            print(f"{name:10s} {cls.description}")
        return 0

    try:
        cfg: Config = load_config(args.config)
    except FileNotFoundError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 2

    inst = ADAPTERS[args.command]()
    opts = {spec.name: getattr(args, spec.name) for spec in inst.options}
    try:
        rt = build_runtime(args.command, cfg, inst.merge_options(opts))
    except KeyError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 2

    try:
        summary = run_job(
            inputs=list(args.inputs),
            adapter=rt.adapter,
            opts=opts,
            backend=rt.backend,
            tool_path=rt.tool_path,
            output_dir=args.output_dir,
            workers=args.workers or cfg.workers,
            retries=cfg.retries if args.retries is None else args.retries,
            timeout_s=args.timeout or cfg.timeout_s,
            log_dir=args.log_dir or Path(cfg.log_dir),
            force=args.force,
            dry_run=args.dry_run,
            progress=_progress_printer,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"오류: {e}", file=sys.stderr)
        return 2

    print()
    print(format_summary(summary))
    if summary.log_path:
        print(f"로그: {summary.log_path}\nJSON: {summary.json_path}")
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
