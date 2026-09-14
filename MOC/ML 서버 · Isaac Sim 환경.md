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

### 4-1. Dockerfile 블록별 해설

#### ⭐ 대전제 — 이미지 안에 GPU 드라이버는 없다

```
호스트 (ml104)                       컨테이너
├── NVIDIA 드라이버 595.84  ───────→  실행 시점에 bind-mount 로 주입
│   (libcuda.so, Vulkan ICD)          (nvidia-container-toolkit 이 수행)
└── docker                            이미지가 담는 것:
                                      └── CUDA runtime/math 라이브러리 (12.8.1)
```
**드라이버(호스트) ≠ CUDA toolkit(이미지).** `nvidia-smi` 의 `CUDA Version: 13.2` 는
드라이버가 지원하는 **최대치**이고, 이미지는 12.8 을 쓰므로 하위 호환으로 동작한다 (§1 에서 실증).

#### `FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04`

| 변종 | 포함 | 판단 |
|---|---|---|
| `base` | `libcudart` 만 | cuBLAS/cuDNN 없음 → torch 불가 |
| **`runtime`** ✅ | + cuBLAS, cuFFT, cuDNN, **nvrtc** | 채택 |
| `devel` | + `nvcc`, 헤더 (+3GB) | torch wheel 은 미리 컴파일되어 불필요 |

> [!tip] `devel` 이 필요해지는 유일한 경우
> 무언가가 **CUDA 커널을 직접 컴파일**할 때. Isaac Lab 의 **NVIDIA Warp** 는 JIT 컴파일을 하지만
> `nvrtc`(runtime 에 포함)를 쓰므로 괜찮다. `nvcc: not found` / `CUDA_HOME` 에러가 나면
> **`runtime` → `devel` 로 한 단어만 바꾸면 된다.**

**왜 22.04 인가** (호스트는 24.04인데):
```
Isaac Sim 5.1 → Python 3.11 로 컴파일 (권장이 아니라 ABI 고정)
Ubuntu 22.04  → 기본 3.10, GLIBC 2.35 ✅ (요구 2.35+)
Ubuntu 24.04  → 기본 3.12. 게다가 패키지가 t64 계열로 개명 (libasound2 → libasound2t64)
```
컨테이너 유저스페이스는 호스트와 완전히 별개다. 커널만 공유한다.

#### ENV 블록

| 변수 | 없으면 |
|---|---|
| `DEBIAN_FRONTEND=noninteractive` | `tzdata` 가 지역 선택 프롬프트를 띄우고 **빌드가 영원히 멈춘다** |
| ⭐ `NVIDIA_DRIVER_CAPABILITIES=all` | 기본값 `compute,utility` 에는 **`graphics` 가 없다** → Vulkan ICD 미주입 → **headless 여도 Kit 초기화에서 사망** |
| `OMNI_KIT_ACCEPT_EULA` 외 2개 | 첫 실행에 EULA 프롬프트 → 비대화형 학습이 멈춤 |
| `PYTHONUNBUFFERED=1` | TTY 가 아니면 stdout 버퍼링 → **로그가 지연되거나 크래시 시 증발** |

> [!danger] `NVIDIA_DRIVER_CAPABILITIES` 가 이 파일에서 가장 중요한 한 줄
> 없을 때 나는 에러(*"Failed to create Vulkan instance"*, *"carb::windowing failed"*)가
> 전부 **GPU 인식 실패처럼 보인다.** `compute` 만으로도 `nvidia-smi` 와 PyTorch 는 정상 동작하므로
> **§1 의 4GB 할당 테스트만으로는 이 항목이 검증되지 않는다.**

#### apt 블록 — 왜 전부 한 `RUN` 인가

`RUN` 하나 = layer 하나. 쪼개면 두 가지가 깨진다:
- **stale index**: `update` layer 가 캐시 히트되면 낡은 목록으로 설치 → `404`
- **크기**: layer 는 추가만 되고 삭제가 소급되지 않는다. `rm -rf /var/lib/apt/lists/*` 는 **같은 RUN 안**이어야 실제로 줄어든다

| 그룹 | 패키지 | 역할 |
|---|---|---|
| PPA 도구 | `software-properties-common ca-certificates gnupg` | `add-apt-repository` + 서명 검증 |
| ⭐ Python | `python3.11{,-dev,-venv,-distutils}` | 22.04 기본은 3.10. **잘못된 버전이면 pip 이 wheel 이 없다며 거부** |
| 빌드 | `build-essential cmake ninja-build` | 공식 문서 명시 (robomimic 요구) |
| ⭐ Vulkan | `libvulkan1 vulkan-tools mesa-vulkan-drivers` | loader + 진단 + fallback ICD |
| GL/EGL | `libgl1 libglu1-mesa libegl1 libgles2 libglib2.0-0` | `libegl1` 은 **headless 오프스크린 렌더링** = `--video` 녹화의 핵심 |
| ⚠️ X11 | `libsm6 libxext6 libxrender1 libxrandr2 libxinerama1 libxcursor1 libxi6 libxkbcommon-x11-0 libxcb-cursor0` | **창을 안 띄워도 필요** |
| Chromium | `libasound2 libnss3 libatk-bridge2.0-0 libgtk-3-0` | Kit 일부 UI 가 내장 CEF |

> [!warning] ⚠️ X11 라이브러리가 headless 에서도 필요한 이유 — Docker 실패 원인 1위
> ```
> Kit 의 .so 들이 이 라이브러리에 링크되어 있다
>         ↓
> 창을 만들 때가 아니라 **모듈 로드 시점**에 해석된다
>         ↓
> error while loading shared libraries: libXrandr.so.2: cannot open shared object file
>         ↓
> import 단계에서 사망. "화면이 없어서" 가 아니다
> ```

**Vulkan 은 loader 와 ICD 가 한 쌍이다:**
```
libvulkan1 (loader) ──찾는다──→ NVIDIA Vulkan ICD
                                  ↑ 호스트 드라이버에서 주입
                                    (NVIDIA_DRIVER_CAPABILITIES=all 필요)
```
둘 중 하나만 있으면 실패한다. ENV 블록과 apt 블록이 **여기서 연결된다.**

#### venv — "컨테이너가 격리인데 왜 또?"

| 이유 | 설명 |
|---|---|
| ⭐ Python 확정 | 이미지에 3.10(시스템)과 3.11(deadsnakes)이 **둘 다** 있다. `pip` 가 어디 붙을지 불확실 |
| `PATH` | `/opt/venv/bin` 을 앞에 두면 `python`·`pip` 가 무조건 3.11 |
| Isaac Lab 연동 | `isaaclab.sh` 가 **활성 venv 를 자동 감지**한다 |
| 충돌 회피 | apt-python 패키지와 pip 패키지가 안 섞인다 |

#### ⭐ pip 설치 — 순서가 핵심

```
isaacsim[all] 은 의존성으로 torch 를 끌고 온다 (기본 빌드)

순서를 바꾸면: torch(cu128) → isaacsim → resolver 가 torch 를 덮어씀 → cu128 아님 → Blackwell 불가
지금 순서:     isaacsim → torch -U 로 cu128 강제 덮어쓰기 → cu128 최종 승리 ✅
```

**`--extra-index-url` 과 `--index-url` 은 다른 옵션이다:**
```
--extra-index-url   PyPI 에 "추가로" 본다   (PyPI + pypi.nvidia.com)
--index-url         PyPI 를 "대체" 한다      (오직 그 저장소)
```
- isaacsim 줄은 `--extra-index-url` — 나머지 의존성(numpy 등)은 PyPI 에 있으므로
- **torch 줄은 `--index-url`** — PyPI 기본 torch 는 다른 CUDA 빌드라, 대체해야 **cu128 이 보장**된다

**`[all,extscache]`**: `extscache` 는 extension 캐시를 **wheel 안에 담아 배포**한다.
없으면 공식 경고에 그대로 걸린다 — *"can take upwards of 10 minutes ... on the first run of each experience file"*.
공용 서버에서는 **되느냐/안 되느냐의 차이**가 된다.

**`--no-cache-dir`**: pip 캐시 15~20GB 를 이미지에 남기지 않는다. 재빌드 시 재다운로드가 대가지만, 한 번 빌드해 계속 쓸 이미지이므로 크기를 택했다.

#### ⭐ 이 이미지에 일부러 안 넣은 것

| 제외 | 이유 |
|---|---|
| **Isaac Lab** | `/workspace` 에 clone. 이미지에 넣으면 **코드 한 줄 고칠 때마다 20분 재빌드** |
| **우리 프로젝트 코드** | 같은 이유. git 관리 + bind-mount |
| f1tenth_gym | Tier 1 은 별개 환경 |

```
이미지 = "거의 안 바뀌는 것" (OS, Python, CUDA, Isaac Sim)  ← 빌드 20분
마운트 = "자주 바뀌는 것"   (Isaac Lab, 우리 코드, 로그)   ← 즉시 반영
```
**이 경계를 잘못 그으면 20분짜리 빌드를 하루에 열 번 하게 된다.**

#### 실패 가능 지점

| # | 지점 | 증상 | 대응 |
|---|---|---|---|
| 1 | `add-apt-repository ppa:deadsnakes` | 빌드 중단 | Python 3.11 포함 베이스로 교체 |
| 2 | 패키지 이름 불일치 | `Unable to locate package` | `apt-cache search` 로 22.04 실제 이름 확인 |
| 3 | `nvcc` 요구 의존성 | `CUDA_HOME not set` | `runtime` → `devel` |
| 4 | 디스크 | `no space left on device` | 40~60GB 필요. `df -h ~` |
| 5 | isaacsim 다운로드 | 타임아웃 | `--timeout 300`, tmux 라 재시도 용이 |

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
