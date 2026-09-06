# comfy-workflow — AI 辅助多风格制图流

> 本工作流由 AI 编程助手(ZCode)全程搭建:环境诊断、模型下载、服务配置、出图脚本、风格系统均由 AI 辅助完成。

机器:RTX 5060 Laptop 8GB / ComfyUI v0.28.0(装在 `D:\Comfy-Desktop`,模型目录 `D:\Comfy-Desktop\ComfyUI-Shared\models`)。

## 出图两步走

**第一步·启动服务**(电脑重启后或服务未运行时做一次;浏览器可访问 http://127.0.0.1:8188):

```bat
scripts\start_comfyui.bat          :: 默认 8188 端口
scripts\start_comfyui.bat 8189     :: 端口被占时换一个
```

服务是独立窗口进程,最小化即可,关掉窗口或 Ctrl+C 即停止服务。

**第二步·出图**(服务常驻期间随时可用;用的是 ComfyUI 自带 Python,不依赖系统 Python):

```bat
D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe scripts\comfy_gen.py --prompt "一只戴宇航员头盔的橘猫" --style photo
```

出好的图自动保存到 `output\`。脚本运行时会打印 `[AI 辅助生成]` 标记,标明本次使用的风格与模型。

## 多风格生成(--style)

风格预设 = 英文风格关键词(叠加到正向提示词)+ 风格干扰排除项(合并进负向提示词)+ 建议尺寸。**内容词可写中文,风格交给预设**,这是实测最稳的写法。

```bat
python scripts\comfy_gen.py --prompt "江南水乡的清晨" --style ink
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

## 可调整的细节

**提示词写法**

- 内容词中文可用的前提是写"具体名词+场景",抽象修饰容易被忽略。
- 构图意图要显式写:想特写就加 `close-up`(或中文"特写"),要全景就写 `wide shot`。SDXL 不会自己猜景别,这是"拿铁变咖啡店全景"的根因。
- 每张图一个主主体;两个以上主体容易顾此失彼。

**采样参数**

| 参数 | 默认 | 调整建议 |
|---|---|---|
| `--steps` | 28 | 20 快速出稿;30~35 精修,超过 35 基本无增益 |
| `--cfg` | 6.5 | 提示词遵循度:4~5 更自由,7~8 更贴提示词但易过饱和 |
| `--sampler` / `--scheduler` | dpmpp_2m / karras | 也可试 `euler`/`euler_ancestral` + `normal`,风格会有差异 |
| `--seed` | 随机 | 固定 seed + 改提示词 = 同构图换内容;好图记下 seed |
| `--negative` | 内置 | 自定义后会与风格排除项自动合并,不用重复写 |

**尺寸与显存**(RTX 5060 8GB 实测)

| 尺寸 | 状态 |
|---|---|
| 1024×1024 | ✅ 实测稳定,约 26 秒/张(28 步) |
| 1536×1536 | ✅ 实测成功,约 44 秒/张,ComfyUI 自动显存卸载兜底 |
| >1536 档(如 2048²) | ⚠️ 未实测,预期明显变慢或有 OOM 风险 |

爆显存时优先降尺寸;仍不行可在启动命令后加 `--lowvram` 重启服务(此参数本机未实测)。

**服务与端口**

- 服务地址默认 `127.0.0.1:8188`;如果端口被(桌面版 ComfyUI 或其他程序)占用,用 `start_comfyui.bat 8189` 换端口启动,出图时加 `--server 127.0.0.1:8189`。
- 与桌面版共用同一套模型目录;但两者不要同时抢 8188。桌面版自动更新 ComfyUI 版本后,建议重跑一次出图验证。
- `--list-checkpoints` 列出所有可用模型,`--checkpoint` 指定;新模型放进 `D:\Comfy-Desktop\ComfyUI-Shared\models\` 对应子目录即可被识别。

## comfy_gen.py 全部参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--prompt` / `-p` | 必填 | 正向提示词(支持中文) |
| `--style` / `-s` | none | 风格预设,见上表 |
| `--negative` / `-n` | 内置 | 负向提示词(自动与风格排除项合并) |
| `--checkpoint` | sd_xl_base_1.0.safetensors | 模型名 |
| `--width/--height` | 风格建议尺寸 | 显式指定则覆盖 |
| `--steps` | 28 | 步数 |
| `--cfg` | 6.5 | 提示词遵循度 |
| `--seed` | 随机 | -1 随机,固定可复现 |
| `--sampler` / `--scheduler` | dpmpp_2m / karras | 采样器/调度器 |
| `--server` | 127.0.0.1:8188 | ComfyUI 服务地址 |
| `--out` | `output/` | 保存目录 |
| `--list-styles` / `--list-checkpoints` | — | 查看风格/模型清单 |

## 目录结构

- `scripts/start_comfyui.bat` — 启动服务(可选端口参数,带模型路径配置)
- `scripts/extra_models_config.yaml` — 把 `D:\Comfy-Desktop\ComfyUI-Shared\models` 挂给无头启动的 ComfyUI
- `scripts/comfy_gen.py` — AI 辅助多风格出图脚本(零依赖,纯标准库)
- `scripts/download_sdxl.sh` — SDXL 四路并行下载(hf-mirror,留作重装备用)
- `output/` — 生成的图片(不入库)

## 已装模型与许可

- `checkpoints/sd_xl_base_1.0.safetensors`(6.5GB,SDXL 文生图,适配 8GB 显存)
- SDXL base 采用 OpenRAIL++ 许可:允许商用,但附带使用限制条款(禁止特定违法用途),分发生成内容时请留意。

## 已知边界

- SDXL 基础模型对多物体/特写构图遵循较弱;风格由预设把控,内容漂移可通过显式构图词(`close-up`、`wide shot`)缓解,换更好的 checkpoint(如各类 SDXL 微调)可显著改善。
- 下载模型走的是 hf-mirror.com(HuggingFace 国内镜像)。
- ComfyUI-Manager 的 SSL 校验已恢复为开启(bypass_ssl=false);若装自定义节点遇到证书报错再考虑临时调整。
