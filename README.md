# comfy-workflow — AI 辅助多风格制图流

> 本工作流由 AI 编程助手(ZCode)全程搭建:环境诊断、模型下载、服务配置、出图脚本、风格系统均由 AI 辅助完成,一条命令出图。

机器:RTX 5060 Laptop 8GB / ComfyUI v0.28.0(装在 `D:\Comfy-Desktop`,模型目录 `D:\Comfy-Desktop\ComfyUI-Shared\models`)。

## 一键出图

```bat
:: 1. 启动服务(保持窗口开着;浏览器可访问 http://127.0.0.1:8188)
scripts\start_comfyui.bat

:: 2. 出图(另开一个终端;用的是 ComfyUI 自带 Python,不依赖系统 Python)
D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe scripts\comfy_gen.py --prompt "一只戴宇航员头盔的橘猫" --style photo
```

出好的图自动保存到 `output\`。脚本运行时会打印 `[AI 辅助生成]` 标记,标明本次生成使用的风格与模型。

## 多风格生成(--style)

风格预设 = 英文风格关键词(叠加到正向提示词)+ 风格干扰排除项(合并进负向提示词)+ 建议尺寸。**内容词可写中文,风格交给预设**,这是实测最稳的写法。

```bat
python scripts\comfy_gen.py --prompt "江南水乡的清晨" --style ink
python scripts\comfy_gen.py --prompt "街角咖啡店的一杯拿铁" --style photo
python scripts\comfy_gen.py --prompt "白发的少女剑客站在樱花树下" --style anime
python scripts\comfy_gen.py --list-styles   :: 查看全部风格
```

| 取值 | 风格 | 建议尺寸 | 说明 |
|---|---|---|---|
| `none` | 原始 | 1024×1024 | 不叠加风格,提示词原样使用 |
| `ink` | 水墨 | 1024×768 | 中国水墨画,黑白留白 |
| `photo` | 写实摄影 | 1024×768 | 照片感,自然光,细节锐利 |
| `anime` | 动漫 | 832×1216 | 日系赛璐璐,竖版构图 |
| `oil` | 油画 | 1024×768 | 古典油画,厚涂笔触 |
| `guofeng` | 国风插画 | 832×1216 | 工笔国风,雅致配色 |
| `cyberpunk` | 赛博朋克 | 1024×768 | 霓虹雨夜,电影感 |
| `3d` | 3D渲染 | 1024×1024 | 影棚柔光,PBR 材质 |
| `sketch` | 素描 | 1024×1024 | 铅笔素描,排线线稿 |

预设定义在 `scripts/comfy_gen.py` 的 `STYLES` 字典里,照着格式加一段就能扩充新风格。

## comfy_gen.py 其他参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--prompt` / `-p` | 必填 | 正向提示词(支持中文) |
| `--negative` / `-n` | 内置 | 负向提示词(自动与风格排除项合并) |
| `--style` / `-s` | none | 风格预设,见上表 |
| `--checkpoint` | sd_xl_base_1.0.safetensors | 模型名,`--list-checkpoints` 可列出全部 |
| `--width/--height` | 风格建议尺寸 | 显式指定则覆盖 |
| `--steps` | 28 | 步数,20~35 |
| `--cfg` | 6.5 | 提示词遵循度,4~8 |
| `--seed` | 随机 | 固定种子可复现同构图 |
| `--out` | `output/` | 保存目录 |

## 目录结构

- `scripts/start_comfyui.bat` — 启动服务(带模型路径配置)
- `scripts/extra_models_config.yaml` — 把 `D:\Comfy-Desktop\ComfyUI-Shared\models` 挂给无头启动的 ComfyUI
- `scripts/comfy_gen.py` — AI 辅助多风格出图脚本(零依赖,纯标准库)
- `scripts/download_sdxl.sh` — SDXL 四路并行下载(hf-mirror,留作重装备用)
- `output/` — 生成的图片(不入库)

## 已装模型

- `checkpoints/sd_xl_base_1.0.safetensors`(6.5GB,SDXL 文生图,适配 8GB 显存)

新模型放到 `D:\Comfy-Desktop\ComfyUI-Shared\models\` 对应子目录(checkpoints / loras / vae …)即可被识别。

## 已知边界

- SDXL 基础模型对"多物体构图/特写意图"遵循较弱(如"一杯拿铁"可能给成咖啡店全景);风格由预设牢牢把控,内容漂移换更好的 checkpoint 可显著改善。
- 8GB 显存跑 SDXL 1024×1024 正常;如果报显存不足,把尺寸降到 896×896 或在启动命令加 `--lowvram`。
- 桌面版 ComfyUI 也可以正常用,两边共用同一个模型目录。
- 下载模型走的是 hf-mirror.com(HuggingFace 国内镜像)。
