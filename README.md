# comfy-workflow — ComfyUI 制图流

机器:RTX 5060 Laptop 8GB / ComfyUI v0.28.0(装在 `D:\Comfy-Desktop`,模型目录 `D:\Comfy-Desktop\ComfyUI-Shared\models`)。

## 一键出图

```bat
:: 1. 启动服务(保持窗口开着;浏览器可访问 http://127.0.0.1:8188)
scripts\start_comfyui.bat

:: 2. 出图(另开一个终端;用的是 ComfyUI 自带 Python,不依赖系统 Python)
D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe scripts\comfy_gen.py --prompt "一只戴宇航员头盔的橘猫, 电影感光线, 高细节"
```

出好的图自动保存到 `output\`。

## comfy_gen.py 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--prompt` / `-p` | 必填 | 正向提示词(支持中文) |
| `--negative` / `-n` | 内置 | 负向提示词 |
| `--checkpoint` | sd_xl_base_1.0.safetensors | 模型名,`--list-checkpoints` 可列出全部 |
| `--width/--height` | 1024×1024 | 尺寸(SDXL 建议 1024 档,如 1024×768) |
| `--steps` | 28 | 步数,20~35 |
| `--cfg` | 6.5 | 提示词遵循度,4~8 |
| `--seed` | 随机 | 固定种子可复现同构图 |
| `--out` | `output/` | 保存目录 |

## 目录结构

- `scripts/start_comfyui.bat` — 启动服务(带模型路径配置)
- `scripts/extra_models_config.yaml` — 把 `D:\Comfy-Desktop\ComfyUI-Shared\models` 挂给无头启动的 ComfyUI
- `scripts/comfy_gen.py` — API 出图脚本(零依赖,标准库)
- `scripts/download_sdxl.sh` — SDXL 四路并行下载(hf-mirror,已用过,留作重装备用)
- `output/` — 生成的图片

## 已装模型

- `checkpoints/sd_xl_base_1.0.safetensors`(6.5GB,SDXL 文生图,适配 8GB 显存)

新模型放到 `D:\Comfy-Desktop\ComfyUI-Shared\models\` 对应子目录(checkpoints / loras / vae …)即可被识别。

## 备注

- 8GB 显存跑 SDXL 1024×1024 正常;如果报显存不足,把尺寸降到 896×896 或在启动命令加 `--lowvram`。
- 桌面版 ComfyUI 也可以正常用,两边共用同一个模型目录。
- 下载模型走的是 hf-mirror.com(HuggingFace 国内镜像)。
