#!/usr/bin/env bash
# 컨테이너 안에서 실행. URDF 생성 → USD 변환 → 검사 → GLB 내보내기.
#
#   bash /workspace/tools/build_racecar_usd.sh
#   bash /workspace/tools/build_racecar_usd.sh --tree      # 검사에 prim 트리 덤프 추가
#   SKIP_GLB=1 bash /workspace/tools/build_racecar_usd.sh  # GLB 생략
#
# ★ 이전 산출물을 반드시 지우고 시작한다.
#   변환이 실패해도 낡은 racecar.usd 가 남아 있으면 "파일이 있다"는 검사가
#   통과해버려 실패를 성공으로 오판한다. 실제로 그렇게 오진한 적이 있다.
set -uo pipefail

IL_DIR="${IL_DIR:-/workspace/IsaacLab}"
ASSETS="${ASSETS:-/workspace/assets}"
TOOLS="$(cd "$(dirname "$0")" && pwd)"
URDF="$ASSETS/racecar_physics.urdf"
USD="$ASSETS/racecar.usd"
TARGET_TYPE="${TARGET_TYPE:-none}"
LOG="${LOG:-/tmp/convert_urdf.log}"

# venv 밖에서 돌려도 동작하도록 python 을 탐색한다
PY="$(command -v python || command -v python3)"
[ -n "$PY" ] || { echo "❌ python 을 찾을 수 없다"; exit 1; }

hr() { printf '\n══ %s\n' "$*"; }
die() { echo "  ❌ $*"; exit 1; }

hr "0. 환경"
echo "  python  = $PY ($("$PY" -V 2>&1))"
echo "  ASSETS  = $ASSETS"
echo "  IL_DIR  = $IL_DIR"
[ -d "$IL_DIR" ] || die "IsaacLab 이 $IL_DIR 에 없다"

hr "1. 이전 산출물 제거 (★ 실패를 성공으로 오판하지 않기 위해)"
mkdir -p "$ASSETS"
rm -rf "$USD" "$ASSETS/configuration" "$ASSETS"/racecar*.glb
echo "  제거: racecar.usd, configuration/, racecar*.glb"

hr "2. URDF 생성"
"$PY" "$TOOLS/gen_racecar_urdf.py" -o "$URDF" || die "생성 실패"
[ -s "$URDF" ] || die "$URDF 가 비어 있다"
echo "  ✅ $(stat -c '%s bytes' "$URDF")  $URDF"
echo "     link $(grep -c '<link ' "$URDF")개 / joint $(grep -c '<joint ' "$URDF")개"

hr "3. URDF → USD 변환  (--joint-target-type $TARGET_TYPE)"
cd "$IL_DIR"
./isaaclab.sh -p scripts/tools/convert_urdf.py "$URDF" "$USD" \
    --headless --joint-target-type "$TARGET_TYPE" > "$LOG" 2>&1
RC=$?
grep -aE "Input URDF file|Generated USD file|Invalid file path|Traceback|ValueError|RuntimeError|\[Error\]" "$LOG" \
  | grep -avEi "MaterialX|libXt|omni\.ext\.plugin|Unresolved reference" | sed 's/^/  /' | head -20
echo "  (전체 로그: $LOG, 종료코드 $RC)"

[ -s "$USD" ] || {
  echo "  ❌ USD 가 생성되지 않았다. 로그 마지막 40줄:"
  tail -40 "$LOG" | sed 's/^/     /'
  exit 1
}
echo "  ✅ 생성된 파일 전부:"
find "$ASSETS" -name '*.usd*' -printf '     %10s  %p\n' 2>/dev/null | sort -k2
echo "     ★ racecar.usd 가 작으면(수 KB) 정상이다 — configuration/*.usd 를 참조하는 스텁이다"

hr "4. USD 검사"
./isaaclab.sh -p "$TOOLS/inspect_usd.py" "$USD" "$@" 2>&1 \
  | grep -avEi "MaterialX|libXt\.so|omni\.ext\.plugin|Could not load the dynamic library|Unresolved reference"
INSPECT_RC=${PIPESTATUS[0]}

if [ "${SKIP_GLB:-0}" != "1" ]; then
  hr "5. GLB 내보내기 (호스트에서 웹 뷰어로 확인용)"
  for mode in both collision; do
    ./isaaclab.sh -p "$TOOLS/usd_to_glb.py" "$USD" \
        -o "$ASSETS/racecar_${mode}.glb" --only "$mode" 2>&1 \
      | grep -avEi "MaterialX|libXt\.so|omni\.ext\.plugin|Could not load|Unresolved reference|^\[INFO\]|^Loading|^\[Info\]" \
      | sed 's/^/  /'
  done
  echo
  echo "  호스트에서:"
  echo "    scp <이름>@192.168.50.112:~/rl-racing/assets/racecar_*.glb ."
fi

hr "결과"
[ "$INSPECT_RC" -eq 0 ] && echo "  ★ 검사 통과" || echo "  ⚠️ 검사에서 지적 사항이 있다 (위 참조)"
