#!/bin/bash
# SDXL base 1.0 四路并行下载 (hf-mirror),分片断点续传,SHA256 总校验。
#
# 运行环境:Windows 必须在 Git Bash 中运行;Linux 终端亦可(同为 GNU 用户态)。
# 不支持 macOS:BSD 用户态没有 GNU stat -c 与 sha256sum,中途必然失败。
# 用法:
#   bash scripts/download_sdxl.sh
#   MODEL_DIR=/path/to/models/checkpoints bash scripts/download_sdxl.sh   # 自定义落盘目录
set -u

URL="https://hf-mirror.com/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors"
TOTAL=6938078334
# 官方公布 SHA256(与 HuggingFace 仓库页一致;已与作者本机已下载副本核对相同)
EXPECTED_SHA256="31e35c80fc4829d14f90153f4c74cd59c90b779f6afe05a74cd6120b893f7e5b"
# 落盘目录可用环境变量 MODEL_DIR 覆盖,默认为本机 ComfyUI-Shared 的 checkpoints 目录
MODEL_DIR="${MODEL_DIR:-/d/Comfy-Desktop/ComfyUI-Shared/models/checkpoints}"
STAGE="$MODEL_DIR/.sdxl_staging"
FINAL="$MODEL_DIR/sd_xl_base_1.0.safetensors"
mkdir -p "$STAGE"

CHUNK=$(( (TOTAL + 3) / 4 ))
pids=()
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
      # 断点续传: 从已有字节继续;单次失败先重试(最多 3 次),失败后以下方尺寸终检为准
      if ! curl -sL --retry 5 --retry-delay 3 -m 2400 \
           -r $(( START + have ))-$END \
           -o "$STAGE/part$i.tmp" "$URL"; then
        echo "WARN: 分片 $i 第 $attempt/3 次尝试下载失败,已保留断点,即将重试" >&2
        sleep 3
        continue
      fi
      cat "$STAGE/part$i.tmp" >> "$STAGE/part$i"
      rm -f "$STAGE/part$i.tmp"
    done
    have=0
    [ -f "$STAGE/part$i" ] && have=$(stat -c %s "$STAGE/part$i")
    want=$(( END - START + 1 ))
    if [ "$have" -lt "$want" ]; then
      echo "ERROR: 分片 $i 下载不完整 ($have/$want 字节),已保留断点;重跑本脚本可续传" >&2
      exit 1
    fi
  ) &
  pids+=($!)
done
FAIL=0
for pid in "${pids[@]}"; do
  wait "$pid" || FAIL=1
done
if [ "$FAIL" -ne 0 ]; then
  echo "ABORT: 存在下载失败的分片,未进行拼合" >&2
  exit 1
fi

# 拼合
cat "$STAGE/part0" "$STAGE/part1" "$STAGE/part2" "$STAGE/part3" > "$FINAL.final"
SIZE=$(stat -c %s "$FINAL.final")
if [ "$SIZE" -ne "$TOTAL" ]; then
  echo "DOWNLOAD_SIZE_MISMATCH got=$SIZE want=$TOTAL" >&2
  # 拼合结果不可用,清掉以免被误认为可用的模型文件(校验失败须重新下载)
  rm -f "$FINAL.final"
  exit 1
fi

# SHA256 总校验(官方公布值)
GOT_SHA256=$(sha256sum "$FINAL.final" | awk '{print $1}')
if [ "$GOT_SHA256" != "$EXPECTED_SHA256" ]; then
  echo "DOWNLOAD_SHA256_MISMATCH got=$GOT_SHA256 want=$EXPECTED_SHA256" >&2
  echo "文件已损坏,请删除后重新下载" >&2
  rm -f "$FINAL.final"
  exit 1
fi

mv -f "$FINAL.final" "$FINAL"
rm -rf "$STAGE"
echo "DOWNLOAD_OK size=$SIZE sha256=$GOT_SHA256"
