#!/usr/bin/env bash
# 컨테이너 안에서 실행. Isaac Lab 을 Isaac Sim 5.1 / Python 3.11 과 맞게 설치한다.
#
#   bash /workspace/tools/setup_isaaclab.sh
#
# ── 왜 이렇게 복잡한가 ────────────────────────────────────────────────
# 1) 태그 고정 (v2.3.2)
#    main 은 Isaac Lab 3.0 + Newton/MuJoCo-Warp 물리 백엔드로 이동 중이다.
#    Tier 2 의 근거가 PhysX 접촉 마찰의 mu*N 포화이므로 엔진을 바꾸면 전제를
#    다시 검증해야 한다. v2.3.2 의 setup.py classifiers 가 Python 3.11 +
#    Isaac Sim 5.1.0 을 명시하는 최신 릴리스다.
#
# 2) stable-baselines3 제외 — 화해 불가능한 충돌
#    isaacsim-core 5.1  ->  torch == 2.7.0  (정확히 고정)
#    stable-baselines3 2.9.0 -> torch >= 2.8
#    pip 이 이 모순을 풀려고 isaaclab 을 backtracking 하다가 인덱스의 엉뚱한
#    후보를 만나 "requires a different Python: not in '>=3.12'" 를 뱉는다.
#    3.12 요구는 증상이고 원인은 torch 충돌이다.
#    skrl(torch>=1.11)과 rsl_rl(torch>=2.6)은 문제 없다. 우리는 skrl 을 쓴다.
#
# 3) torch 를 마지막에 재고정
#    isaaclab.sh 의 ensure_cuda_torch() 가 torch/torchvision/torchaudio 를
#    uninstall 한 뒤 -U 로 재설치하는데, torchaudio 는 지우기만 하고 다시 깔지
#    않는다. isaacsim-core 5.1 은 torchaudio==2.7.0 을 요구한다.
#
# 4) --no-deps fallback
#    isaaclab.sh 는 소스 패키지를 find -exec 로 설치하므로 하나가 실패해도
#    조용히 넘어가고 종료코드가 묻힌다. 그래서 import 로 직접 확인하고,
#    실패하면 resolver 를 완전히 우회해서(--no-deps) 로컬 패키지만 강제 설치한다.
set -uo pipefail

IL_TAG="${IL_TAG:-v2.3.2}"
IL_DIR="${IL_DIR:-/workspace/IsaacLab}"
FRAMEWORK="${FRAMEWORK:-skrl}"
IDX="https://download.pytorch.org/whl/cu128"
TORCH=2.7.0 TV=0.22.0 TA=2.7.0
PKGS="isaaclab isaaclab_assets isaaclab_mimic isaaclab_rl isaaclab_tasks"

hr() { printf '══ %s\n' "$*"; }

hr "1. torch 2.7.0 과 공존 불가한 패키지 제거"
pip uninstall -y stable-baselines3 rl-games 2>/dev/null | tail -2 || true

hr "2. Isaac Lab 을 ${IL_TAG} 로 체크아웃"
[ -d "$IL_DIR/.git" ] || git clone https://github.com/isaac-sim/IsaacLab.git "$IL_DIR"
cd "$IL_DIR"
git fetch --tags --force origin >/dev/null 2>&1
git checkout -q "$IL_TAG"
echo "  현재: $(git describe --tags --always)"

hr "3. isaaclab.sh --install ${FRAMEWORK}"
./isaaclab.sh --install "$FRAMEWORK" 2>&1 | tail -25
echo "  (종료코드가 묻히는 구조이므로 아래에서 import 로 직접 확인한다)"

hr "4. import 확인"
if python -c "import isaaclab" 2>/dev/null; then
  echo "  ✅ isaaclab import 성공"
else
  echo "  ⚠️ 실패 → resolver 를 우회해 로컬 패키지만 강제 설치한다"
  for d in $PKGS; do
    printf "    %-18s " "$d"
    pip install -q --no-deps -e "$IL_DIR/source/$d" && echo "ok" || echo "FAILED"
  done
  echo "  런타임 의존성 설치 (sb3 제외)"
  pip install -q "numpy<2" "onnx>=1.18.0" "prettytable==3.3.0" toml \
      "hidapi==0.14.0.post2" "gymnasium==1.2.1" trimesh "pyglet<2" einops \
      "warp-lang" "pillow==11.3.0" "starlette==0.49.1" \
      pytest pytest-mock junitparser "flatdict==4.0.1" flaky packaging \
    && echo "    ok" || echo "    ⚠️ 일부 실패"
  pip install -q "skrl[torch]" && echo "    skrl ok" || echo "    ⚠️ skrl 실패"
fi

hr "5. torch 3종 재고정 (isaacsim-core 5.1 의 요구)"
pip install -q -U --index-url "$IDX" "torch==$TORCH" "torchvision==$TV" "torchaudio==$TA" \
  && echo "  ok"

hr "6. isaacsim-kernel 의 정확 핀 복원"
# isaacsim-kernel 5.1 은 이 세 개를 == 로 고정한다. isaaclab 설치가 올려버린다.
pip install -q "click==8.1.7" "psutil==5.9.8" "typing_extensions==4.12.2" && echo "  ok"

hr "7. 검증"
python - <<'PY'
import importlib, sys
print(f"  python      {sys.version.split()[0]}")
for m in ("torch","torchvision","torchaudio"):
    print(f"  {m:<11} {importlib.import_module(m).__version__}")
import torch
print(f"  cuda        {torch.cuda.is_available()}  devices={torch.cuda.device_count()}")
ok = True
for m in ("isaacsim","isaaclab","isaaclab_assets","isaaclab_tasks","skrl"):
    try:
        importlib.import_module(m); print(f"  ✅ import {m}")
    except Exception as e:
        ok = False; print(f"  ❌ import {m}  -> {type(e).__name__}: {e}")
pin = (torch.__version__.startswith("2.7.0")
       and importlib.import_module("torchvision").__version__.startswith("0.22.0")
       and importlib.import_module("torchaudio").__version__.startswith("2.7.0"))
print("  torch 핀 " + ("✅" if pin else "❌ isaacsim 이 깨진다"))
sys.exit(0 if (ok and pin) else 1)
PY
IMPORT_OK=$?

echo; echo "  ── pip check ──"
pip check 2>&1 | sed 's/^/  /' || true
echo "  (sb3/rl-games 관련 줄이 사라져 있어야 정상. 나머지는 대개 무해)"

hr "8. Isaac Lab 스모크 테스트"
if [ "$IMPORT_OK" -eq 0 ]; then
  ./isaaclab.sh -p scripts/tutorials/00_sim/create_empty.py --headless --device cuda:0 \
    && echo "  ✅ Isaac Lab 정상 기동" || echo "  ❌ 기동 실패 — 위 로그 확인"
else
  echo "  건너뜀 (7단계 import 가 실패했다)"
fi
