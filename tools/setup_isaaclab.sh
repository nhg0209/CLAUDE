#!/usr/bin/env bash
# 컨테이너 안에서 실행. Isaac Lab 을 Isaac Sim 5.1 / Python 3.11 과 맞는 태그로 설치한다.
#
#   bash /workspace/tools/setup_isaaclab.sh
#
# 왜 태그를 고정하는가:
#   - main 은 Isaac Lab 3.0 으로 이동 중이고 Newton/MuJoCo-Warp 물리 백엔드를 쓴다.
#     우리가 Tier 2 로 가는 근거는 PhysX 접촉 마찰의 mu*N 포화이므로,
#     물리 엔진이 바뀌면 그 전제를 다시 검증해야 한다. 지금은 바꾸지 않는다.
#   - v2.3.2 의 setup.py classifiers 가 Python 3.11 + Isaac Sim 5.1.0 을 명시한다.
#
# 왜 설치 후에 torch 를 다시 고정하는가:
#   isaaclab.sh 의 install_torch() 가
#       pip uninstall torch torchvision torchaudio
#       pip install -U --index-url .../cu128 torch==<ver> torchvision==<ver>
#   를 실행한다. -U 로 우리 핀을 덮어쓰고, torchaudio 는 지우기만 하고 다시 깔지 않는다.
#   그런데 isaacsim-core 5.1 은 torch/torchaudio==2.7.0, torchvision==0.22.0 을 "정확히" 요구한다.
set -euo pipefail

IL_TAG="${IL_TAG:-v2.3.2}"
IL_DIR="${IL_DIR:-/workspace/IsaacLab}"
IDX="https://download.pytorch.org/whl/cu128"
TORCH=2.7.0 TV=0.22.0 TA=2.7.0

echo "══ 1. Isaac Lab 을 ${IL_TAG} 로 체크아웃 ══"
if [ ! -d "$IL_DIR/.git" ]; then
  git clone https://github.com/isaac-sim/IsaacLab.git "$IL_DIR"
fi
cd "$IL_DIR"
git fetch --tags --force origin
git checkout -q "$IL_TAG"
echo "  현재: $(git describe --tags --always)"

echo; echo "══ 2. isaaclab.sh --install ══"
echo "  (torch 를 건드릴 것이다. 3단계에서 되돌린다)"
./isaaclab.sh --install || echo "  ⚠️ 비정상 종료 — 3단계 후 pip check 로 판단한다"

echo; echo "══ 3. torch 3종을 isaacsim 5.1 요구대로 재고정 ══"
pip install -U --index-url "$IDX" "torch==$TORCH" "torchvision==$TV" "torchaudio==$TA"

echo; echo "══ 4. 검증 ══"
python - <<'PY'
import torch, torchvision, torchaudio
print(f"  torch       {torch.__version__}")
print(f"  torchvision {torchvision.__version__}")
print(f"  torchaudio  {torchaudio.__version__}")
print(f"  cuda        {torch.cuda.is_available()}  devices={torch.cuda.device_count()}")
if torch.cuda.is_available():
    for i in range(torch.cuda.device_count()):
        print(f"    [{i}] {torch.cuda.get_device_name(i)}")
ok = torch.__version__.startswith("2.7.0") and torchvision.__version__.startswith("0.22.0") \
     and torchaudio.__version__.startswith("2.7.0")
print("  torch 핀 " + ("✅ 일치" if ok else "❌ 불일치 — isaacsim 이 깨진다"))
PY
echo
echo "  ── pip check (남은 의존성 충돌) ──"
pip check 2>&1 | sed 's/^/  /' || true

echo; echo "══ 5. Isaac Lab 스모크 테스트 ══"
./isaaclab.sh -p scripts/tutorials/00_sim/create_empty.py --headless --device cuda:0 \
  && echo "  ✅ Isaac Lab 정상" \
  || echo "  ❌ 실패 — 위 로그 확인"
