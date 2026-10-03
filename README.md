# comfy-workflow — AI 辅助多风格制图流

> 本工作流由 AI 编程助手(ZCode)全程搭建:环境诊断、模型下载、服务配置、出图脚本、风格系统均由 AI 辅助完成。

> 文中实测数据(出图耗时、显存表现)来自作者的 RTX 5060 Laptop 8GB / ComfyUI v0.28.0 环境;`D:\Comfy-Desktop\...` 等路径均为该机器的示例,换机器请按下方「前提条件」修改配置,脚本与配置本身不含必须绑定特定机器的逻辑。

## 前提条件

- 已安装 ComfyUI(桌面版或手动部署均可),知道其程序目录(含 `main.py`)与自带 venv 的 `python.exe` 位置。
- 首次在本机使用时改两处配置:
  1. `scripts/start_comfyui.bat` 顶部「可配置区」的 `PY` / `CWD`;
  2. `scripts/extra_models_config.yaml` 的 `base_path`(指向本机共享模型根目录)。
- `scripts/download_sdxl.sh` 需在 Git Bash(Windows)中运行;Linux 终端亦可(同为 GNU 用户态);**不支持 macOS**(其 BSD 用户态缺少脚本依赖的 `stat -c` 与 `sha256sum`)。
- 模型需自备:可用 `scripts/download_sdxl.sh` 下载 SDXL base 1.0,或把已有模型放进 `base_path` 对应的子目录。
- 启动服务一律使用本仓库 `scripts\start_comfyui.bat`:它固定加载**脚本同目录**的 `extra_models_config.yaml`。若机器上还留有本仓库的其他旧副本,请勿用旧副本里的脚本启动,以免模型挂错目录。

## 出图两步走

**第一步·启动服务**(电脑重启后或服务未运行时做一次;浏览器可访问 http://127.0.0.1:8188):

```bat
scripts\start_comfyui.bat
scripts\start_comfyui.bat 8189
```

第一条默认 8188 端口;端口被(桌面版 ComfyUI 或其他程序)占用时,在后面跟上端口号换一个,如第二条的 8189。端口之后还可以附加任意 `main.py` 参数(见下方 `--lowvram` 用法)。

服务是独立窗口进程,最小化即可,关掉窗口或 Ctrl+C 即停止服务。

**第二步·出图**(服务常驻期间随时可用;跑 `comfy_gen.py` 用任意 Python 3 即可,纯标准库、无第三方依赖;若系统 Python 不在 PATH,用 ComfyUI 自带 venv 的 python.exe 同样可以):

```bat
python scripts\comfy_gen.py --prompt "一只戴宇航员头盔的橘猫" --style photo
```

出好的图自动保存到 `output\`。脚本运行时会打印 `[AI 辅助生成]` 标记,标明本次使用的风格与模型。

## 多风格生成(--style)

风格预设 = 英文风格关键词(叠加到正向提示词)+ 风格干扰排除项(合并进负向提示词)+ 建议尺寸。**内容词可写中文,风格交给预设**,这是实测最稳的写法。

```bat
python scripts\comfy_gen.py --prompt "江南水乡的清晨" --style ink
python scripts\comfy_gen.py --prompt "白发的少女剑客站在樱花树下" --style anime
python scripts\comfy_gen.py --list-styles
```

第三条查看全部风格。风格一览:

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

**尺寸与显存**(作者机器 RTX 5060 8GB 实测)

| 尺寸 | 状态 |
|---|---|
| 1024×1024 | ✅ 实测稳定,约 26 秒/张(28 步) |
| 1536×1536 | ✅ 实测成功,约 44 秒/张,ComfyUI 自动显存卸载兜底 |
| >1536 档(如 2048²) | ⚠️ 未实测,预期明显变慢或有 OOM 风险 |

爆显存时优先降尺寸;仍不行可重启服务并附加 `--lowvram` 参数(写在端口之后):

```bat
scripts\start_comfyui.bat 8188 --lowvram
```

(`--lowvram` 参数本机未实测,效果因卡而异。)

**服务与端口**

- 服务地址默认 `127.0.0.1:8188`;端口被占时用 `start_comfyui.bat 8189` 换端口启动,出图时加 `--server 127.0.0.1:8189`。
- 与桌面版共用同一套模型目录;但两者不要同时抢 8188。桌面版自动更新 ComfyUI 版本后,建议重跑一次出图验证。
- `--list-checkpoints` 列出所有可用模型,`--checkpoint` 指定;新模型放进 `base_path`(见 `scripts/extra_models_config.yaml`)对应的子目录即可被识别。

## comfy_gen.py 全部参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--prompt` / `-p` | 必填 | 正向提示词(支持中文) |
| `--style` / `-s` | none | 风格预设,见上表 |
| `--negative` / `-n` | 内置 | 负向提示词(自动与风格排除项合并) |
| `--checkpoint` | sd_xl_base_1.0.safetensors | 模型名 |
| `--width/--height` | 风格建议尺寸 | 显式指定则覆盖;需 ≥64 且为 8 的倍数,建议成对指定(只改一边会得到非常规比例) |
| `--steps` | 28 | 步数(≥1) |
| `--cfg` | 6.5 | 提示词遵循度(>0) |
| `--seed` | 随机 | 任意负数均为随机(如 `-1`);给定 ≥0 的值则固定可复现 |
| `--sampler` / `--scheduler` | dpmpp_2m / karras | 采样器/调度器 |
| `--server` | 127.0.0.1:8188 | ComfyUI 服务地址(带 `http://` 前缀会被自动剥掉;不支持 `https://`,会直接报错) |
| `--out` | `output/` | 保存目录(多图时按 subfolder 分子目录保存,不会互相覆盖) |
| `--timeout` | 900 | 轮询出图结果的超时秒数;慢机器大尺寸出图可调大 |
| `--list-styles` / `--list-checkpoints` | — | 查看风格/模型清单 |

## 目录结构

- `scripts/start_comfyui.bat` — 启动服务(第 1 参为端口号,之后可附加 `main.py` 参数;顶部集中可配置)
- `scripts/extra_models_config.yaml` — 把本机共享模型目录挂给无头启动的 ComfyUI(`base_path` 按机器修改)
- `scripts/comfy_gen.py` — AI 辅助多风格出图脚本(零依赖,纯标准库)
- `scripts/download_sdxl.sh` — SDXL 四路并行下载(hf-mirror,SHA256 校验,留作重装备用)
- `tests/` — 纯标准库单元测试与 mock 端到端测试(`python -m unittest discover tests`)
- `output/` — 生成的图片(不入库)

## 已装模型与许可

- `checkpoints/sd_xl_base_1.0.safetensors`(6.5GB,SDXL 文生图,适配 8GB 显存)
- SDXL base 采用 OpenRAIL++ 许可(正文:[CreativeML Open RAIL++-M License](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/LICENSE.md)):允许商用,但附带使用限制条款——禁止将其用于法律所禁止的用途及许可中列明的伤害性场景(如生成用于骚扰、诽谤、欺诈等内容),再分发模型须随附同许可;向第三方交付或分发生成内容前,请自行确认条款对具体场景的适用性。

## 已知边界

- SDXL 基础模型对多物体/特写构图遵循较弱;风格由预设把控,内容漂移可通过显式构图词(`close-up`、`wide shot`)缓解,换更好的 checkpoint(如各类 SDXL 微调)可显著改善。
- 下载模型走的是 hf-mirror.com(HuggingFace 国内镜像)。
- ComfyUI-Manager 的 SSL 校验已恢复为开启(bypass_ssl=false);若装自定义节点遇到证书报错再考虑临时调整。
