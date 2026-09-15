#!/usr/bin/env bash
# Isaac Sim 5.1 컨테이너 실행.
#   ./run.sh                     → bash
#   ./run.sh python /workspace/foo.py
#   GPUS=0 ./run.sh bash         → GPU 0번만
#   NAME=aux ./run.sh bash       → 두 번째 셸을 동시에 열 때
set -uo pipefail

USER_NAME="${USER:-$(id -un)}"
IMAGE="${IMAGE:-isaac-rl:$USER_NAME}"
GPUS="${GPUS:-all}"
WS="${WS:-$HOME/rl-racing}"

# 이름 충돌 회피: 같은 이름이 이미 쓰이고 있으면 -2, -3 … 을 붙인다
BASE="isaac-${NAME:-$USER_NAME}"
CNAME="$BASE"; n=2
while docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$CNAME"; do
  CNAME="$BASE-$n"; n=$((n+1))
done

# TTY 가 없는 곳(스크립트, cron, 파이프)에서 -it 를 주면 실패한다
TTY_FLAGS="-i"
[ -t 0 ] && [ -t 1 ] && TTY_FLAGS="-it"

# --gpus all 과 --gpus "device=0" 은 문법이 다르다
if [ "$GPUS" = "all" ]; then GPU_FLAG="--gpus all"; else GPU_FLAG="--gpus device=$GPUS"; fi

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "❌ 이미지가 없다: $IMAGE" >&2
  echo "   docker build -t $IMAGE -f docker/Dockerfile ." >&2
  exit 1
fi

mkdir -p "$WS" "$HOME"/.cache/isaac/{ov,glcache,computecache,nvomni,ovdata}

exec docker run $TTY_FLAGS --rm \
  --name "$CNAME" \
  ${GPU_FLAG} \
  -e NVIDIA_DRIVER_CAPABILITIES=all \
  -e OMNI_KIT_ACCEPT_EULA=YES -e ACCEPT_EULA=Y -e PRIVACY_CONSENT=Y \
  -e OMNI_KIT_ALLOW_ROOT=1 \
  -e PYTHONUNBUFFERED=1 \
  --shm-size=16g \
  -v "$WS:/workspace" \
  -v "$HOME/.cache/isaac/ov:/root/.cache/ov" \
  -v "$HOME/.cache/isaac/glcache:/root/.cache/nvidia/GLCache" \
  -v "$HOME/.cache/isaac/computecache:/root/.nv/ComputeCache" \
  -v "$HOME/.cache/isaac/nvomni:/root/.nvidia-omniverse" \
  -v "$HOME/.cache/isaac/ovdata:/root/.local/share/ov/data" \
  -w /workspace \
  "$IMAGE" "${@:-bash}"
