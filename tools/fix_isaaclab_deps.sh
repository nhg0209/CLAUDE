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
inst "flatdict==4.0.1"      "flatdict==4.0.1"    # ← setuptools<82 제약이 필요한 놈
inst flaky                  flaky
inst packaging              "packaging>=24.0"
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

echo; echo "══ 6. import 검증 ══"
python - <<'PY'
import importlib, sys
import torch
print(f"  torch {torch.__version__}  cuda={torch.cuda.is_available()}  devices={torch.cuda.device_count()}")
bad=[]
for m in ("isaacsim","isaaclab","isaaclab_assets","isaaclab_tasks","isaaclab_rl","skrl","warp"):
    try:
        importlib.import_module(m); print(f"  ✅ {m}")
    except Exception as e:
        bad.append(m); print(f"  ❌ {m}  -> {type(e).__name__}: {e}")
sys.exit(1 if bad else 0)
PY
IMPORT_OK=$?

echo; echo "  ── pip check ──"
pip check 2>&1 | sed 's/^/  /' || true

echo; echo "══ 7. 스모크 테스트 ══"
if [ "$IMPORT_OK" -eq 0 ]; then
  cd /workspace/IsaacLab && \
  ./isaaclab.sh -p scripts/tutorials/00_sim/create_empty.py --headless --device cuda:0 \
    && echo "  ✅ Isaac Lab 정상 기동" || echo "  ❌ 기동 실패 — 위 로그 확인"
else
  echo "  건너뜀 (6단계 import 실패)"
fi
