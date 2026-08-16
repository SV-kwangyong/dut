#!/usr/bin/env bash
# Wine 검증 스파이크 — 스펙 §4. 실행 예:
#   docker run --rm -it -v wineprefix:/opt/wineprefix -v /opt/tools:/opt/tools:ro -v /mnt/qumulo:/mnt/qumulo \
#     misc_converter:spike spike.sh /opt/tools/AptivFileConversion_v2.1.5/AptivFileConversion.exe \
#     /opt/tools/DJLPConvertTool/DJLPConvertTool_update7.exe /mnt/qumulo/.../sample.dvl [/mnt/qumulo/.../sample.avi]
# 판정: 각 단계 PASS/FAIL 표. FAIL한 exe는 그 시점에 대안 재결정(스펙 §4 실패 분기).
set -u
APTIV=${1:?AptivFileConversion.exe 경로}
DJLP=${2:?DJLPConvertTool_update7.exe 경로}
DVL=${3:?샘플 .dvl 경로}
AVI=${4:-}
OUT=${SPIKE_OUT:-/tmp/spike_out}
mkdir -p "$OUT"
export WINEPREFIX=${WINEPREFIX:-/opt/wineprefix} WINEDEBUG=-all
declare -A R

step() { echo; echo "═══ $1"; }
winpath() { printf 'Z:%s\n' "$1" | tr '/' '\\'; }

step "0. wineprefix 초기화 (최초 1회 수 분)"
if [ ! -f "$WINEPREFIX/system.reg" ]; then wineboot -u >/dev/null 2>&1; fi
echo "wine: $(wine --version)"

step "1. .NET 런타임 — wine-mono(자동 설치) 확인, 없으면 msi 수동 설치, 최후 winetricks --force dotnet461"
has_mono() { wine uninstaller --list 2>/dev/null | grep -qi "wine mono"; }
has_dotnet() { wine uninstaller --list 2>/dev/null | grep -qi "Microsoft .NET Framework 4"; }
echo "prefix arch: $(grep -m1 '#arch' "$WINEPREFIX/system.reg" 2>/dev/null || echo '?')"
if has_mono; then R[dotnet]="PASS (wine-mono 자동 설치)"
else
  MSI=$(ls /usr/share/wine/mono/*.msi 2>/dev/null | head -1)
  if [ -n "$MSI" ] && wine msiexec /i "$MSI" /qn >"$OUT/wine_mono_install.log" 2>&1 && has_mono; then R[dotnet]="PASS (wine-mono msi 수동 설치)"
  elif winetricks -q --force dotnet461 >"$OUT/winetricks_dotnet461.log" 2>&1 && has_dotnet; then R[dotnet]="PASS (winetricks dotnet461 --force)"
  else R[dotnet]="FAIL ($OUT/wine_mono_install.log, winetricks_dotnet461.log 확인)"; fi
fi
echo "${R[dotnet]}"; echo "--- 설치된 런타임:"; wine uninstaller --list 2>/dev/null | grep -iE "mono|\.NET" | head -5

step "2. AptivFileConversion --help (콘솔 모드 기동)"
if timeout 120 xvfb-run -a wine "$(winpath "$APTIV")" --help 2>&1 | tee "$OUT/aptiv_help.txt" | grep -q -- "--asc"; then
  R[aptiv_help]=PASS; else R[aptiv_help]=FAIL; fi
echo "${R[aptiv_help]}"

step "3. AptivFileConversion dvl→asc 실변환"
rm -f "$OUT/$(basename "${DVL%.*}").asc"
timeout 900 xvfb-run -a wine "$(winpath "$APTIV")" -i "$(winpath "$DVL")" -o "$(winpath "$OUT")" -y --asc --ascbase=hex --asctimeref=absolute \
  > "$OUT/aptiv_run.txt" 2>&1
ASC="$OUT/$(basename "${DVL%.*}").asc"
if [ -s "$ASC" ]; then R[aptiv_convert]="PASS ($(stat -c%s "$ASC") bytes)"; echo "--- head:"; head -3 "$ASC"; else R[aptiv_convert]="FAIL (aptiv_run.txt 확인)"; fi
echo "${R[aptiv_convert]}"

step "4. DJLPConvertTool --help (Qt CLI 모드 기동)"
if timeout 120 xvfb-run -a wine "$(winpath "$DJLP")" --help > "$OUT/djlp_help.txt" 2>&1; then R[djlp_help]="PASS"; else R[djlp_help]="FAIL/미지원 (djlp_help.txt 확인)"; fi
echo "${R[djlp_help]}"; echo "--- 출력(옵션 표면 실측용):"; head -40 "$OUT/djlp_help.txt"

if [ -n "$AVI" ]; then
  step "5. DJLPConvertTool avi→raw 실변환 (실측 CLI: -s <PATH>)"
  timeout 900 xvfb-run -a wine "$(winpath "$DJLP")" -s "$(winpath "$AVI")" > "$OUT/djlp_run.txt" 2>&1
  RAW="$(dirname "$AVI")/$(basename "${AVI%.*}").raw"
  if [ -s "$RAW" ]; then R[djlp_convert]="PASS"; else R[djlp_convert]="FAIL (djlp_run.txt 확인 — argv 템플릿 조정 필요할 수 있음)"; fi
  echo "${R[djlp_convert]}"
fi

step "판정 요약"
for k in dotnet aptiv_help aptiv_convert djlp_help djlp_convert; do [ -n "${R[$k]:-}" ] && printf "  %-14s %s\n" "$k" "${R[$k]}"; done
echo "산출물·로그: $OUT"
