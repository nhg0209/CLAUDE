#!/usr/bin/env bash
# isaaclab 의 런타임 의존성을 하나씩 설치한다. 멱등(idempotent)하므로 여러 번 돌려도 된다.
#
#   bash /workspace/tools/fix_isaaclab_deps.sh
#
# ── 왜 하나씩 설치하는가 ──────────────────────────────────────────────
# pip 은 인자로 받은 목록을 원자적으로 처리한다. 하나가 실패하면 전부 설치되지 않는다.
# flatdict==4.0.1 은 sdist 만 배포하므로 빌드가 필요한데, 빌드 격리 환경이 최신
# setuptools(84.x)를 설치하고 setuptools 82 부터 pkg_resources 가 제거되어
# flatdict 의 setup.py 가 죽는다. 그 결과 warp-lang 까지 같이 설치되지 않았다.
# (IsaacLab 자신의 pyproject 도 setuptools<82.0.0 을 요구한다 — 같은 문제의 흔적)
#
# ── isaacsim-kernel 의 == 핀을 복원하지 않는 이유 ─────────────────────
# click 8.5.0 / psutil 7.2.2 / typing_extensions 4.16.0 상태에서 isaacsim --help 와
# import isaacsim 이 모두 정상 동작했다. 반면 == 로 내리면 onnx 가
# typing_extensions>=4.15.0 을 요구해 실제로 깨지고, ipython/wandb/huggingface-hub
# 도 함께 충돌한다. 그 핀은 load-bearing 이 아니므로 최신을 유지한다.
set -uo pipefail

IDX="https://download.pytorch.org/whl/cu128"
CONSTRAINT=/tmp/il_constraint.txt
echo "setuptools<82" > "$CONSTRAINT"   # 빌드 격리 환경에도 적용된다

ok=(); fail=()
inst() {  # inst <표시명> <pip 인자...>
  local name="$1"; shift
  printf "  %-26s " "$name"
  if PIP_CONSTRAINT="$CONSTRAINT" pip install -q "$@" 2>/tmp/il_err.txt; then
    echo "ok"; ok+=("$name")
  else
    echo "FAILED"; fail+=("$name"); sed 's/^/      /' /tmp/il_err.txt | tail -3
  fi
}

echo "══ 1. 블로커 먼저 — warp-lang (isaaclab_assets / isaaclab_tasks 가 요구) ══"
inst warp-lang warp-lang

echo; echo "══ 2. isaaclab v2.3.2 의 나머지 런타임 의존성 (하나씩) ══"
inst "numpy<2"              "numpy<2"
inst "onnx>=1.18.0"         "onnx>=1.18.0"
inst "prettytable==3.3.0"   "prettytable==3.3.0"
inst toml                   toml
inst "hidapi"               "hidapi==0.14.0.post2"
inst "gymnasium==1.2.1"     "gymnasium==1.2.1"   # isaaclab 이 == 로 요구. 현재 1.3.0
inst trimesh                trimesh
inst "pyglet<2"             "pyglet<2"
inst einops                 einops
inst "pillow==11.3.0"       "pillow==11.3.0"
inst "starlette==0.49.1"    "starlette==0.49.1"
inst "flatdict==4.1.0"      "flatdict==4.1.0"    # 4.0.1 은 sdist 뿐이라 빌드 실패. 4.1.0 은 wheel 이 있다
inst flaky                  flaky
inst "packaging==23.0"      "packaging==23.0"    # isaacsim-core 가 ==23.0, isaaclab_rl 이 <24 를 요구한다.
                                                  # wheel 의 >=24.0 경고는 빌드 시점 전용이라 무해하다
inst pytest                 pytest pytest-mock junitparser
# transformers 는 크고 우리는 vision 기능을 쓰지 않는다. 실패해도 무해
inst "transformers(선택)"    "transformers==4.57.6"

echo; echo "══ 3. isaacsim-kernel 의 == 핀 되돌리기 (위 주석 참조) ══"
inst "typing_extensions"    -U "typing_extensions>=4.15.0"
inst "click"                -U "click>=8.4.2,<9"
inst "psutil"               -U "psutil>=7"

echo; echo "══ 4. torch 3종 재고정 (isaacsim-core 5.1 이 == 로 요구) ══"
inst "torch 3종" -U --index-url "$IDX" torch==2.7.0 torchvision==0.22.0 torchaudio==2.7.0

echo; echo "══ 5. 결과 ══"
printf "  성공 %d개" "${#ok[@]}"; [ ${#fail[@]} -gt 0 ] && printf " / 실패: %s" "${fail[*]}"; echo

echo; echo "══ 6. pip check ══"
pip check 2>&1 | sed 's/^/  /' || true
cat <<'NOTE'
  ── 남아도 되는 경고 ──
   daqp / dex-retargeting / pin-pink : humanoid retargeting 전용. 우리는 안 쓴다
   isaacsim-kernel 의 click/psutil/typing_extensions == 핀 : 그 없이도 정상 동작 확인됨.
       내리면 onnx(typing_extensions>=4.15.0)가 실제로 깨진다
   fastapi vs starlette : livestream 전용. 우리는 headless + 영상 녹화를 쓴다
NOTE

echo; echo "══ 7. 검증은 AppLauncher 를 띄운 뒤에 해야 한다 ══"
cat <<'NOTE'
  pxr(OpenUSD)은 AppLauncher 가 sys.path 에 올려준다. 맨몸 import 는 실패하는 것이 정상.
  ⚠️ pip install usd-core 로 채우려 하지 말 것 — Isaac Sim 번들 USD 와 충돌한다.

  다음을 실행하라:
    cd /workspace/IsaacLab
    ./isaaclab.sh -p /workspace/tools/verify_isaaclab.py
NOTE
