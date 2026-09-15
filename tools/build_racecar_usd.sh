#!/usr/bin/env bash
# 컨테이너 안에서 실행. URDF 생성 → USD 변환 → 검사를 한 번에.
#
#   bash /workspace/tools/build_racecar_usd.sh
#
# convert_urdf.py 는 입력 경로가 없으면 ValueError: Invalid file path 를 던지는데
# Kit 시작 로그(수십 줄)에 묻혀 보이지 않는다. 그래서 각 단계를 명시적으로 확인한다.
set -uo pipefail

IL_DIR="${IL_DIR:-/workspace/IsaacLab}"
ASSETS="${ASSETS:-/workspace/assets}"
TOOLS="$(cd "$(dirname "$0")" && pwd)"
URDF="$ASSETS/racecar_physics.urdf"
USD="$ASSETS/racecar.usd"

hr() { printf '\n══ %s\n' "$*"; }

hr "1. 작업 디렉터리"
mkdir -p "$ASSETS"
echo "  ASSETS = $ASSETS"
echo "  TOOLS  = $TOOLS"
[ -d "$IL_DIR" ] || { echo "  ❌ IsaacLab 이 $IL_DIR 에 없다"; exit 1; }

hr "2. URDF 생성 (표준 라이브러리만 쓰므로 어디서든 돈다)"
python "$TOOLS/gen_racecar_urdf.py" -o "$URDF" || { echo "  ❌ 생성 실패"; exit 1; }
if [ ! -s "$URDF" ]; then echo "  ❌ $URDF 가 비어 있다"; exit 1; fi
echo "  ✅ $(ls -la "$URDF" | awk '{print $5" bytes  "$NF}')"
echo "  link $(grep -c '<link ' "$URDF")개 / joint $(grep -c '<joint ' "$URDF")개"

hr "3. URDF → USD 변환"
echo "  입력: $URDF"
echo "  출력: $USD"
cd "$IL_DIR"
# Kit 로그가 방대하므로 전체는 파일로 남기고 화면에는 중요한 줄만 띄운다
LOG=/tmp/convert_urdf.log
./isaaclab.sh -p scripts/tools/convert_urdf.py "$URDF" "$USD" \
    --headless --joint-target-type none > "$LOG" 2>&1
RC=$?
grep -E "Input URDF file|Generated USD file|Invalid file path|Error|Traceback|ValueError|Exception" "$LOG" \
  | grep -viE "MaterialX|libXt|omni.ext.plugin" | sed 's/^/  /' | head -20
echo "  (전체 로그: $LOG)"

if [ ! -s "$USD" ]; then
  echo "  ❌ USD 가 생성되지 않았다 (종료코드 $RC). 전체 로그 마지막 40줄:"
  tail -40 "$LOG" | sed 's/^/     /'
  exit 1
fi
echo "  ✅ $(ls -la "$USD" | awk '{print $5" bytes  "$NF}')"

hr "4. USD 검사"
./isaaclab.sh -p "$TOOLS/inspect_usd.py" "$USD" 2>&1 \
  | grep -viE "MaterialX|libXt.so|omni\.ext\.plugin|Could not load the dynamic library"
