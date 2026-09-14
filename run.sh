#!/usr/bin/env bash
# Isaac Sim 5.1 컨테이너 실행. 인자를 넘기면 그 명령을, 없으면 bash 를 연다.
#   ./run.sh bash
#   ./run.sh python /workspace/foo.py
set -euo pipefail
mkdir -p "$HOME"/.cache/isaac/{ov,glcache,computecache,nvomni,ovdata}
docker run -it --rm \
  --name "isaac-$USER" \
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
  "isaac-rl:$USER" "${@:-bash}"
