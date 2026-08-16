"""AptivFileConversion.exe v2.1.5 어댑터 — DVL/DVS/MUDP/ASC/MF4 → ASC/DVL/DVS/LCM/MUDP/PCAP/ADTF.

옵션 표면은 `AptivFileConversion.exe --help` 실측(2026-08-16) 기준. 라이터 7종을 전부 노출한다.
exe는 WinForms 기반이라 exit code를 신뢰할 수 없어(실패해도 0 가능) 성공 판정은 산출물 존재로만 한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from misc_converter.adapters.base import Adapter, OptionSpec
from misc_converter.backends.base import Backend
from misc_converter.engine.models import WorkItem

# 입력 포맷 선택값 → 확장자. 기본 dvl(실사용 주 경로). "any"는 전부.
INPUT_FORMATS: dict[str, tuple[str, ...]] = {
    "dvl": (".dvl",),
    "dvs": (".dvs", ".dvss", ".dvsu"),
    "mudp": (".mudp",),
    "asc": (".asc",),
    "mf4": (".mf4",),
}
INPUT_EXTENSIONS = {ext for exts in INPUT_FORMATS.values() for ext in exts}

# 라이터 플래그 → 기대 출력 확장자. None = 문서·바이너리에서 확인 불가(실측 전) → verify가 stem.* 신규 파일로 판단
WRITERS: dict[str, str | None] = {
    "asc": ".asc",
    "dvl": ".dvl",
    "dvs": None,  # --dvsextension 옵션값(기본 dvs)으로 결정
    "lcm": None,
    "mudp": ".mudp",
    "pcap": ".pcap",
    "adtf": None,
}

# 라이터별 부속 옵션(exe에 `--name=value`로 전달). 라이터 플래그가 켜진 경우에만 전달한다.
WRITER_SUBOPTIONS: dict[str, tuple[str, ...]] = {
    "asc": ("ascbase", "asctimeref"),
    "dvl": ("dvlversion",),
    "dvs": ("dvsextension", "dvssectionname", "dvssectionsize"),
    "lcm": ("lcmvideo1",),
    "mudp": ("ethernetmap", "ethsrcmac", "ethdestmac", "ethsrcip", "ethdestip", "ethsrcport", "ethdestport"),
    "pcap": ("pcapmtu", "ethernetmap", "ethsrcmac", "ethdestmac", "ethsrcip", "ethdestip", "ethsrcport", "ethdestport"),
    "adtf": (),
}


class AptivAdapter(Adapter):
    name = "aptiv"
    description = "AptivFileConversion — dvl/dvs/mudp/asc/mf4 → asc/dvl/dvs/lcm/mudp/pcap/adtf"
    unit = "file"
    tool_key = "aptiv"
    backend_kind = "wine"
    options = [
        OptionSpec(
            "input_format", "choice", "dvl", (*INPUT_FORMATS.keys(), "any"), "입력 포맷 필터(트리 스캔 시 이 확장자만)"
        ),
        OptionSpec("asc", "flag", False, help="ASC 내보내기 (CAN 텍스트 트레이스, 주력 경로)"),
        OptionSpec("ascbase", "choice", "hex", ("hex", "dec"), "ASC 숫자 표기"),
        OptionSpec("asctimeref", "choice", "absolute", ("absolute", "relative"), "ASC 타임스탬프 기준"),
        OptionSpec("dvl", "flag", False, help="DVL 내보내기"),
        OptionSpec(
            "dvlversion",
            "choice",
            "v32",
            ("v20", "v21", "v22", "v23", "vCANZ", "v30", "v31", "v31a", "v32"),
            "출력 DVL 버전",
        ),
        OptionSpec("dvs", "flag", False, help="DVS 내보내기"),
        OptionSpec("dvsextension", "str", "dvs", help="DVS 출력 확장자"),
        OptionSpec("dvssectionname", "str", "DXDAQ0", help="DVS 섹션 이름(8자 이하)"),
        OptionSpec("dvssectionsize", "int", 1500, help="DVS 섹션 크기(byte)"),
        OptionSpec("lcm", "flag", False, help="LCM 내보내기"),
        OptionSpec("lcmvideo1", "str", None, help="LCM 입력의 주 비디오 채널명"),
        OptionSpec("mudp", "flag", False, help="MUDP 내보내기"),
        OptionSpec("ethernetmap", "choice", "default", ("default", "custom", "radars", "adasEcu"), "이더넷 매핑 방식"),
        OptionSpec("ethsrcmac", "str", None, help="소스 MAC"),
        OptionSpec("ethdestmac", "str", None, help="목적지 MAC"),
        OptionSpec("ethsrcip", "str", None, help="소스 IP"),
        OptionSpec("ethdestip", "str", None, help="목적지 IP"),
        OptionSpec("ethsrcport", "int", 50014, help="소스 UDP 포트"),
        OptionSpec("ethdestport", "int", 50015, help="목적지 UDP 포트"),
        OptionSpec("pcap", "flag", False, help="PCAP 내보내기"),
        OptionSpec("pcapmtu", "int", 1500, help="PCAP MTU(byte)"),
        OptionSpec("adtf", "flag", False, help="ADTF 내보내기"),
    ]

    def match(self, path: Path, opts: dict[str, Any]) -> bool:
        if not path.is_file():
            return False
        fmt = str(opts.get("input_format") or "dvl")
        allowed = INPUT_EXTENSIONS if fmt == "any" else set(INPUT_FORMATS.get(fmt, ()))
        return path.suffix.lower() in allowed

    def enabled_writers(self, opts: dict[str, Any]) -> list[str]:
        return [w for w in WRITERS if opts.get(w)]

    def build_argv(self, item: WorkItem, opts: dict[str, Any], tool_path: str, backend: Backend) -> list[str]:
        writers = self.enabled_writers(opts)
        if not writers:
            raise ValueError("출력 포맷을 하나 이상 지정해야 합니다 (--asc, --dvl, ...)")
        # -y: 스킵 판정은 엔진이 이미 끝냈으므로 exe에는 무조건 덮어쓰기 — 부분 산출물 재생성 보장
        argv = [tool_path, "-i", backend.tool_path(item.source), "-o", backend.tool_path(item.output_dir), "-y"]
        seen: set[str] = set()
        for w in writers:
            argv.append(f"--{w}")
            for sub in WRITER_SUBOPTIONS[w]:
                if sub in seen:
                    continue
                seen.add(sub)
                val = opts.get(sub)
                if val is not None and val != "":
                    argv.append(f"--{sub}={val}")
        return argv

    def expected_outputs(self, item: WorkItem, opts: dict[str, Any]) -> list[Path]:
        outs: list[Path] = []
        for w in self.enabled_writers(opts):
            ext = WRITERS[w]
            if w == "dvs":
                ext = "." + str(opts.get("dvsextension") or "dvs").lstrip(".")
            if ext is None:
                # 미실측 라이터가 섞여 있으면 확정 목록을 만들 수 없다 → 빈 리스트(verify는 stem.* 근거)
                return []
            outs.append(item.output_dir / f"{item.stem}{ext}")
        return outs
