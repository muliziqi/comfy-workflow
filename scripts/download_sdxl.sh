#!/bin/bash
# SDXL base 1.0 四路并行下载 (hf-mirror),完成后拼合校验
set -u
URL="https://hf-mirror.com/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors"
TOTAL=6938078334
STAGE="/d/Comfy-Desktop/ComfyUI-Shared/models/checkpoints/.sdxl_staging"
FINAL="/d/Comfy-Desktop/ComfyUI-Shared/models/checkpoints/sd_xl_base_1.0.safetensors"
mkdir -p "$STAGE"

CHUNK=$(( (TOTAL + 3) / 4 ))
for i in 0 1 2 3; do
  START=$(( i * CHUNK ))
  END=$(( START + CHUNK - 1 ))
  if [ $END -ge $TOTAL ]; then END=$(( TOTAL - 1 )); fi
  (
    for attempt in 1 2 3; do
      have=0
      [ -f "$STAGE/part$i" ] && have=$(stat -c %s "$STAGE/part$i")
      want=$(( END - START + 1 ))
      [ "$have" -ge "$want" ] && break
      # 断点续传: 从已有字节继续
      curl -sL --retry 5 --retry-delay 3 -m 2400 \
        -r $(( START + have ))-$END \
        -o "$STAGE/part$i.tmp" "$URL" && \
        { cat "$STAGE/part$i.tmp" >> "$STAGE/part$i"; rm -f "$STAGE/part$i.tmp"; }
    done
  ) &
done
wait

# 拼合
cat "$STAGE/part0" "$STAGE/part1" "$STAGE/part2" "$STAGE/part3" > "$FINAL.final"
SIZE=$(stat -c %s "$FINAL.final")
if [ "$SIZE" -eq "$TOTAL" ]; then
  mv -f "$FINAL.final" "$FINAL"
  rm -rf "$STAGE"
  echo "DOWNLOAD_OK size=$SIZE"
else
  echo "DOWNLOAD_SIZE_MISMATCH got=$SIZE want=$TOTAL"
  exit 1
fi
