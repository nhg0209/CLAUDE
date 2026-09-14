#!/usr/bin/env bash
# 컨테이너 안에서 실행. Isaac Sim 이 뜰 수 있는 상태인지 한 번에 진단한다.
echo "══ 1. PyTorch / CUDA ══"
python -c "import torch;print(' ',torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))" 2>&1 | tail -2

echo; echo "══ 2. Vulkan ICD 파일 (NVIDIA 것이 있어야 함) ══"
ls -1 /usr/share/vulkan/icd.d/ /etc/vulkan/icd.d/ 2>/dev/null | sed 's/^/  /'

echo; echo "══ 3. Vulkan 디바이스 ── ★ 여기가 핵심 ══"
# NVIDIA ICD 만 강제해서 mesa 노이즈를 제거
NV_ICD=$(ls /usr/share/vulkan/icd.d/nvidia_icd.json /etc/vulkan/icd.d/nvidia_icd.json 2>/dev/null | head -1)
if [ -n "$NV_ICD" ]; then
  VK_ICD_FILENAMES="$NV_ICD" vulkaninfo --summary 2>/dev/null \
    | sed -n '/Devices:/,$p' | grep -E "GPU|deviceName|driverName|apiVersion|deviceType" | sed 's/^/  /'
else
  echo "  ✗ nvidia_icd.json 없음 → NVIDIA_DRIVER_CAPABILITIES 에 graphics 가 안 들어갔다"
fi

echo; echo "══ 4. 전체 디바이스 (mesa 포함) ══"
vulkaninfo --summary 2>/dev/null | sed -n '/Devices:/,$p' | grep -E "GPU|deviceName" | sed 's/^/  /'

echo; echo "══ 5. root 실행 허용 플래그 ══"
echo "  OMNI_KIT_ALLOW_ROOT=${OMNI_KIT_ALLOW_ROOT:-<미설정 ← Kit 이 segfault 한다>}"

echo; echo "══ 6. Isaac Sim import ══"
python -c "import isaacsim; print('  isaacsim import OK')" 2>&1 | tail -2
