---
tags: [MOC, infra, isaac-sim, tier2]
작성일: 2026-09-14
상태: STEP 0 검증 완료 (2026-09-14) — 빌드 단계
---

# ML 서버 · Isaac Sim 환경 구축

> [!info] 이 노트의 위치
> [[프로젝트 스택]] §11(3-Tier) 의 **Tier 2 를 실행 가능하게 만드는** 환경 문서.
> §12-4 리스크 #2(선형 타이어 모델)의 해결 경로이기도 하다.

> [!success] 검증 상태 — STEP 0 전 항목 통과 (2026-09-14)
> Isaac Sim/Isaac Lab 정보는 공식 저장소에서 확인. **서버 쪽도 실측 완료.** 아래 §1 표 참조.

---

## 1. 하드웨어 — 판정: Tier 2 가능 ✅

`ML_SERVER_USER.md` (Hyeongjoon, 2026-08-31) 기준.

| 항목 | 값 | Isaac Sim 5.1 요구 | 판정 |
|---|---|---|---|
| GPU | **RTX PRO 6000 Blackwell, VRAM 96 GB** | 16 GB 이상 | ✅ 과잉 충족 |
| CPU | Ryzen 9 9950X (16C/32T) | — | ✅ |
| RAM | 64 GB | 32 GB 이상 | ✅ |
| 디스크 | 1.8 TB (여유 1.7 TB) | 이미지 40~60 GB | ✅ |
| OS | Ubuntu 24.04 | 22.04 권장 | ⚠️ **컨테이너를 22.04 로** |
| 드라이버 | ✅ **595.84** (실측) | 580.65.06 이상 권장 | ✅ **여유 충족** |

### ★ STEP 0 실측 결과 (2026-09-14, `hyeonggyun@ml104`, `192.168.50.112`)

```
GPU            NVIDIA RTX PRO 6000 Blackwell Workstation Edition
VRAM           97,887 MiB   (사용 중 16 MiB, util 0%)
Driver         595.84       ← 권장 580.65.06 이상 충족
nvidia-smi     CUDA Version: 13.2  (드라이버 레벨)
```

| 검사 | 결과 |
|---|---|
| rootless docker 이미지 pull | ✅ |
| `--gpus all` + `NVIDIA_DRIVER_CAPABILITIES=all` 로 컨테이너 GPU 접근 | ✅ |
| **`torch 2.8.0+cu128` 로 GPU 4 GB 실제 할당** | ✅ `mem_get_info = (96.9 GB free, 102 GB total)` |
| `hostname -I` | `192.168.50.112` ✅ (`172.17.0.1` 은 docker 브리지) |

> [!note] 드라이버 CUDA 13.2 vs 우리가 쓰는 cu128
> 하위 호환으로 정상 동작함이 **위 4 GB 할당 테스트로 실증**되었다. 추측이 아니다.

> [!warning] `[GPU:512M]` 프롬프트는 허수다
> 쉘 프롬프트에 `[GPU:512M]` 이 뜨지만 **`PS1` 에 문자열로 하드코딩**되어 있고
> (`\[\e[38;5;245m\][GPU:512M]\[\e[0m\]`), `~/.bashrc` · `/etc/profile.d/` grep 결과가 비었으며,
> 실제로 4 GB 할당이 성공하고 96.9 GB 가용이 보고된다.
> **할당량이 아니라 관리자가 박아둔 장식/낡은 표시.** 무시할 것.

> [!question] ⚠️ 미확인 — GPU 가 2장일 가능성
> `--format=csv` 출력에 **동일 행이 2개** 나왔다 (`nvidia-smi` 표는 `head -12` 로 잘림).
> 안내 문서의 *"추후 2장으로 변경 예정"* 이 반영됐을 수 있다. `nvidia-smi -L` 로 확인할 것.
>
> **2장이면 전략이 달라진다**: Isaac Lab 한 판을 두 장에 쪼개는 것보다
> `CUDA_VISIBLE_DEVICES` 로 한 장씩 잡아 **서로 다른 seed/하이퍼파라미터를 동시 실행**하는 편이 낫다.
> → [[SAC (Haarnoja 2018)]] §5 의 *"seed 5개 min/max 밴드"* 프로토콜을 절반 시간에 채울 수 있다.

---

## 2. ⭐ 핵심 발견 — Isaac Sim 5.1 은 pip 설치가 된다

```bash
pip install "isaacsim[all,extscache]==5.1.0" --extra-index-url https://pypi.nvidia.com
pip install -U torch==2.7.0 torchvision==0.22.0 --index-url https://download.pytorch.org/whl/cu128
```

**`nvcr.io` 컨테이너 경로(NGC 계정 + API 키 + EULA 동의 + gated pull)를 전부 우회한다.**
→ rootless Docker 에서 **본인 Dockerfile 로 재현 가능하게** 빌드할 수 있다.

| 확인된 제약 | 값 |
|---|---|
| **Python** | **3.11 고정** (Isaac Sim 5.X → 3.11, 4.X → 3.10) |
| PyTorch | `2.7.0` + `cu128` — Blackwell 의 CUDA 12.8+ 요구와 일치 |
| Isaac Lab 호환 | `main` / `v2.3.X` ↔ Isaac Sim 4.5 / 5.0 / 5.1 |
| GLIBC | 2.35+ (Ubuntu 22.04 = 2.35 ✅) |

---

## 3. STEP 0 — 먼저 확인 (하나라도 실패하면 뒤가 무의미)

```bash
ssh <이름>@192.168.50.112          # 비밀번호 hmc2020, hmcl_2G/5G 또는 유선에서만

nvidia-smi                          # ① 드라이버 580.65.06 이상?
docker context ls                   # ② rootless 인지
docker info | grep -iE "rootless|storage driver|docker root"

# ③ ★ 컨테이너에서 GPU 그래픽 기능이 열리는가 — Isaac Sim 의 생사
docker run --rm --gpus all -e NVIDIA_DRIVER_CAPABILITIES=all \
  nvidia/cuda:12.8.1-base-ubuntu22.04 nvidia-smi

df -h ~                             # ④ 여유 공간 (40~60 GB 필요)
sudo apt install -y tmux htop       # ⑤ 장시간 학습 필수
```

> [!danger] ★ `NVIDIA_DRIVER_CAPABILITIES=all` 을 빠뜨리면 반드시 실패한다
> `--gpus all` 만 주면 컨테이너에 **`compute,utility` 만** 열린다.
> Isaac Sim 은 **headless 여도 Vulkan/OpenGL(`graphics` capability)** 이 필요해 **Kit 초기화에서 죽는다.**
> 이 오류를 "GPU 인식 실패" 로 오진하는 것이 가장 흔한 함정이다.

---

## 4. Dockerfile

`~/rl-racing/docker/Dockerfile`:

```dockerfile
# Blackwell(sm_120) -> CUDA 12.8+ 필수. Isaac Sim 5.1 -> Ubuntu 22.04 + Python 3.11
FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=all \
    OMNI_KIT_ACCEPT_EULA=YES \
    ACCEPT_EULA=Y \
    PRIVACY_CONSENT=Y \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      software-properties-common ca-certificates curl wget git gnupg \
 && add-apt-repository -y ppa:deadsnakes/ppa && apt-get update \
 && apt-get install -y --no-install-recommends \
      python3.11 python3.11-dev python3.11-venv python3.11-distutils \
      build-essential cmake ninja-build \
      libvulkan1 vulkan-tools mesa-vulkan-drivers \
      libgl1 libglu1-mesa libegl1 libgles2 libglib2.0-0 \
      libsm6 libxext6 libxrender1 libxrandr2 libxinerama1 \
      libxcursor1 libxi6 libxkbcommon-x11-0 libxcb-cursor0 \
      libasound2 libnss3 libatk-bridge2.0-0 libgtk-3-0 \
 && rm -rf /var/lib/apt/lists/*

RUN python3.11 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN pip install --no-cache-dir --upgrade pip wheel setuptools

# 공식 문서 순서 그대로: isaacsim 먼저, torch 나중
RUN pip install --no-cache-dir "isaacsim[all,extscache]==5.1.0" \
      --extra-index-url https://pypi.nvidia.com
RUN pip install --no-cache-dir -U torch==2.7.0 torchvision==0.22.0 \
      --index-url https://download.pytorch.org/whl/cu128

WORKDIR /workspace
CMD ["bash"]
```

```bash
tmux new -s build                   # 15~20 GB 다운로드. 반드시 tmux 안에서
cd ~/rl-racing && docker build -t isaac-rl:$USER -f docker/Dockerfile .
# Ctrl+b d 로 분리, tmux attach -t build 로 복귀
```

> [!tip] 빌드 중 실패하기 쉬운 지점
> `add-apt-repository -y ppa:deadsnakes/ppa` — 프록시/DNS 로 막히면 여기서 죽는다.
> 그 경우 Python 3.11 이 이미 든 베이스 이미지로 교체하는 편이 빠르다.

---

## 5. 실행 스크립트

`~/rl-racing/run.sh`:

```bash
#!/usr/bin/env bash
docker run -it --rm \
  --name isaac-$USER \
  --gpus all \
  -e NVIDIA_DRIVER_CAPABILITIES=all \
  -e OMNI_KIT_ACCEPT_EULA=YES -e ACCEPT_EULA=Y -e PRIVACY_CONSENT=Y \
  --shm-size=16g \
  -v "$HOME/rl-racing:/workspace" \
  -v "$HOME/.cache/isaac/ov:/root/.cache/ov" \
  -v "$HOME/.cache/isaac/glcache:/root/.cache/nvidia/GLCache" \
  -v "$HOME/.cache/isaac/computecache:/root/.nv/ComputeCache" \
  -v "$HOME/.cache/isaac/nvomni:/root/.nvidia-omniverse" \
  -v "$HOME/.cache/isaac/ovdata:/root/.local/share/ov/data" \
  -w /workspace \
  isaac-rl:$USER "$@"
```

```bash
mkdir -p ~/.cache/isaac/{ov,glcache,computecache,nvomni,ovdata}
chmod +x ~/rl-racing/run.sh
```

> [!warning] ★ 캐시 마운트는 선택이 아니다
> 공식 문서: *"all dependent extensions will be pulled from the registry. This process can take **upwards of 10 minutes** and is required on the first run of each experience file."*
> `--rm` 을 쓰는 이상 캐시를 마운트하지 않으면 **컨테이너를 띄울 때마다 10분**을 날린다.

**스모크 테스트**
```bash
./run.sh bash
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
#  -> 2.7.0+cu128 True NVIDIA RTX PRO 6000 Blackwell ...
vulkaninfo --summary | head -20     # Vulkan 디바이스가 보여야 함
isaacsim --help
```

---

## 6. Isaac Lab

```bash
cd /workspace                        # = ~/rl-racing (컨테이너를 지워도 남는다)
git clone https://github.com/isaac-sim/IsaacLab.git
cd IsaacLab
./isaaclab.sh --install              # rl_games, rsl_rl, sb3, skrl, robomimic

# 검증 (공식)
./isaaclab.sh -p scripts/tutorials/00_sim/create_empty.py --headless

# SAC 계열 학습이 실제로 도는지
./isaaclab.sh -p scripts/reinforcement_learning/skrl/train.py \
  --task Isaac-Cartpole-v0 --headless --num_envs 64
```

---

## 7. 시각화 — 스트리밍은 불가능, 영상 녹화로

`ML_SERVER_USER.md`: *"다른 PC에서 이 서버의 컨테이너로 접속 → 안 됨"*

Isaac Sim WebRTC 스트리밍은 **외부 → 컨테이너 inbound** 이고 **UDP** 를 쓴다.
`ssh -L` 은 TCP 전용 → **우회 불가.**

| 용도 | 방법 | 가능? |
|---|---|---|
| 학습 | `--headless` | ✅ GUI 불필요 |
| 주행 확인 | `--video --video_length 200 --video_interval 2000` → `scp` | ✅ **권장** |
| 학습 곡선 | `tensorboard --port 6006 --bind_all` + `ssh -L 6006:localhost:6006` | ✅ TCP 라 터널됨 |
| 실시간 GUI | WebRTC 스트리밍 | ❌ |
| 최후 수단 | `docker context use default` + 포트 공개 | ⚠️ 이름에 `$USER`, `-u $(id -u):$(id -g)` 필수 |

---

## 8. ⚠️ 공유 GPU 예절

**96 GB 한 장을 연구실 전체가 쓴다.** Isaac Lab 기본값은 `num_envs` 가 4096 까지 간다 → 혼자 다 먹는다.

```bash
nvidia-smi ; w                       # 돌리기 전 항상
--num_envs 1024                      # 감으로 4096 쓰지 말 것
```
⚠️ `PYTORCH_CUDA_ALLOC_CONF` 는 PyTorch 텐서에만 걸린다. **PhysX 메모리는 `num_envs` 로만 조절된다** — 실질적인 유일한 노브.
다른 사람 프로세스는 죽일 수 없으므로(문서 §프로세스) **내가 먼저 양보하는 수밖에 없다.**

---

## 9. ★ 전략 판단 — GPU 가 생겼다고 Tier 2 가 공짜가 된 게 아니다

> [!danger] Isaac Lab 에는 F1TENTH 도 레이싱 환경도 없다
> 공식 환경 30여 개는 manipulator / quadruped / humanoid 다. 우리가 직접 만들어야 할 것:
> - 차량을 **USD articulation** 으로 (섀시 + 4휠 조인트 + 서보 조향)
> - 트랙 (기존 맵 → mesh/USD 변환)
> - LiDAR — Isaac Lab `RayCaster` 센서로 가능 ✅
> - observation / reward / termination 을 `DirectRLEnv` 로 작성
>
> **수 주 분량.** 비용이 *GPU 부족* 에서 ***저작(authoring) 노동*** 으로 옮겨간 것이다.

> [!tip] 그럼에도 §12-4 리스크 #2 는 이걸로 실제로 풀린다
> PhysX 의 접지력은 **$\mu N$ 으로 포화한다.** §8-5-1 에서 계산한
> *"$\mu=0.08$ 에서 $\beta=-40°$ 인데 모델은 태연히 코너를 돈다"* 가 **일어나지 않는다.**
> → **"미끄러우면 더 꺾어라" 의 부호 반전을 Tier 2 는 실제로 보여준다.**
> ⭐ **Isaac Sim 을 쓰는 진짜 이유는 렌더링 품질이 아니라 타이어 모델이다.**

### 권고: 선택 C (병행)

```
f1tenth_gym (Tier 1) → 알고리즘·reward·관측 설계를 빠르게 반복 (1878 steps/s = 9분/1M)
Isaac Sim  (Tier 2) → 한계 거동 학습 + 최종 policy. 저작 비용 감수
```

**Tier 1 을 버리지 말 것.** Isaac Lab 환경을 만드는 수 주 동안 **아무 학습도 못 하게 된다.**

---

## 🔗 연결

- [[프로젝트 스택]] §8-5-1(선형 타이어 정량 확인) · §11(3-Tier) · §12-4(리스크 #2)
- [[SAC v2 (Haarnoja 2018)]] — 이 환경에서 돌릴 알고리즘
- [[Domain Randomization]] · [[질문 로그]]
