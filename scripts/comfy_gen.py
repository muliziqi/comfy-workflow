#!/usr/bin/env python3
"""ComfyUI API 出图脚本 (SDXL 文生图) — AI 辅助多风格绘图。

由 AI 编程助手 (ZCode) 搭建与维护,支持多风格预设一键切换。

用法:
  python comfy_gen.py --prompt "一只戴宇航员头盔的橘猫" --style ink
  python comfy_gen.py --prompt "江南水乡的清晨" --style photo --width 1024 --height 768
  python comfy_gen.py --list-styles
  python comfy_gen.py --list-checkpoints

依赖: 仅 Python 3 标准库。
"""
import argparse
import json
import os
import random
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SERVER = "127.0.0.1:8188"
CLIENT_ID = "zcode_comfy_gen"

NEG_DEFAULT = "text, watermark, low quality, blurry, deformed hands, ugly"


def _fix_windows_console():
    """cmd 默认 GBK 代码页,切到 UTF-8 避免中文输出乱码。"""
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# 多风格预设:风格词用英文(SDXL 响应更准),内容词可中文。
# 每个风格自带:英文风格关键词 suffix、需排除的干扰项 negative_add、建议尺寸。
# ---------------------------------------------------------------------------
STYLES = {
    "none": dict(
        name="原始", suffix="", negative_add="", w=1024, h=1024,
        desc="不叠加风格,提示词原样使用"),
    "ink": dict(
        name="水墨", w=1024, h=768,
        suffix="traditional chinese ink wash painting, shuimo, monochrome black ink on rice paper, sumi-e brushwork, vast negative space, minimalist masterpiece",
        negative_add="color, colorful, anime, illustration, 3d render, photo, photorealistic",
        desc="中国水墨画,黑白留白,独钓寒江式意境"),
    "photo": dict(
        name="写实摄影", w=1024, h=768,
        suffix="photorealistic, professional photography, 85mm lens, natural lighting, sharp focus, high detail",
        negative_add="illustration, painting, anime, cartoon, 3d render, cgi",
        desc="写实照片感,自然光,细节锐利"),
    "anime": dict(
        name="动漫", w=832, h=1216,
        suffix="anime style, cel shading, vibrant colors, clean line art, studio quality, detailed background",
        negative_add="photo, photorealistic, realistic, sketch",
        desc="日系动漫赛璐璐风,竖版构图"),
    "oil": dict(
        name="油画", w=1024, h=768,
        suffix="oil painting, thick impasto brush strokes, canvas texture, classical composition, rich colors",
        negative_add="photo, photorealistic, anime, 3d render",
        desc="古典油画,厚涂笔触与画布纹理"),
    "guofeng": dict(
        name="国风插画", w=832, h=1216,
        suffix="chinese gongbi style illustration, elegant oriental aesthetics, flowing lines, muted traditional colors, decorative details",
        negative_add="photo, photorealistic, western style",
        desc="工笔国风插画,雅致传统配色,竖版构图"),
    "cyberpunk": dict(
        name="赛博朋克", w=1024, h=768,
        suffix="cyberpunk, neon lights, rain-soaked night streets, holographic signs, high contrast, blade runner atmosphere, cinematic lighting",
        negative_add="",
        desc="霓虹雨夜,电影感高对比"),
    "3d": dict(
        name="3D渲染", w=1024, h=1024,
        suffix="3d render, octane render, soft studio lighting, subsurface scattering, physically based materials, high detail",
        negative_add="photo, painting, sketch, anime",
        desc="三维渲染,影棚柔光,PBR 材质"),
    "sketch": dict(
        name="素描", w=1024, h=1024,
        suffix="pencil sketch, graphite drawing on paper, cross hatching, monochrome, hand drawn line art",
        negative_add="color, colorful, photo, 3d render, anime",
        desc="铅笔素描,排线,手绘线稿"),
}


def api(path, payload=None, timeout=30):
    url = f"http://{SERVER}{path}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    else:
        req = url
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def clean_server(value):
    """清洗 --server 取值:剥离 http(s):// 前缀与尾部斜杠,只留 host:port。"""
    v = (value or "").strip()
    low = v.lower()
    if low.startswith("https://"):
        v = v[8:]
    elif low.startswith("http://"):
        v = v[7:]
    return v.rstrip("/")


def resolve_size(width, height, style):
    """宽高语义:--width/--height 未指定(None)时取风格建议尺寸;显式给出(哪怕 0)则原样采用。"""
    w = width if width is not None else style["w"]
    h = height if height is not None else style["h"]
    return w, h


def _http_error_detail(exc):
    """防御式解析 HTTPError 响应体:是 JSON 才提取 error/node_errors,否则截断打印原文。"""
    try:
        raw = exc.read().decode("utf-8", errors="replace")
    except Exception:
        return ""
    try:
        body = json.loads(raw)
    except Exception:
        return raw.strip()[:500]
    if isinstance(body, dict):
        parts = []
        if body.get("error"):
            parts.append(f"error={body['error']}")
        if body.get("node_errors"):
            parts.append("node_errors=" +
                         json.dumps(body["node_errors"], ensure_ascii=False)[:1500])
        if parts:
            return "; ".join(parts)
        return json.dumps(body, ensure_ascii=False)[:500]
    return str(body)[:500]


def _explain_url_error(exc):
    """把 URLError 翻译成可操作的中文提示。"""
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, ConnectionRefusedError) or "ConnectionRefusedError" in str(reason) \
            or "10061" in str(reason):
        return ("[连接失败] 无法连接 ComfyUI 服务。请先运行 scripts/start_comfyui.bat 启动服务,"
                "或确认 --server 指向的 host:port 正确。")
    if isinstance(reason, socket.gaierror) or "getaddrinfo" in str(reason):
        return ("[地址错误] --server 需写成 host:port 形式(如 127.0.0.1:8188),"
                "不要带 http:// 或 https:// 前缀,主机名也需能解析。")
    if isinstance(reason, socket.timeout) or "timed out" in str(reason):
        return "[超时] 连接 ComfyUI 超时,服务可能正忙或已无响应。"
    return f"[网络错误] {exc}"


def api_or_die(path, payload=None, timeout=30, context="请求"):
    """api() 的容错包装:网络/HTTP 错误翻译成中文提示后以非零码退出。"""
    try:
        return api(path, payload, timeout)
    except urllib.error.HTTPError as e:
        msg = f"[HTTP {e.code}] {context}失败:{e.reason}"
        detail = _http_error_detail(e)
        if detail:
            msg += f"\n{detail}"
        print(msg, file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(_explain_url_error(e), file=sys.stderr)
        sys.exit(1)
    except socket.timeout:
        print(f"[超时] {context}超时。", file=sys.stderr)
        sys.exit(1)


def _try_interrupt():
    """尽力 POST /interrupt 通知服务器停止当前任务;失败不影响退出流程。"""
    try:
        api("/interrupt", {}, timeout=5)
    except Exception:
        pass


def build_workflow(p, neg, w, h, steps, cfg, seed, sampler, scheduler, ckpt):
    """SDXL 文生图最小工作流 (API 格式)。"""
    return {
        "1": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "CLIPTextEncode",
              "inputs": {"text": neg, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode",
              "inputs": {"text": p, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage",
              "inputs": {"width": w, "height": h, "batch_size": 1}},
        "5": {"class_type": "KSampler",
              "inputs": {"seed": seed, "steps": steps, "cfg": cfg,
                         "sampler_name": sampler, "scheduler": scheduler,
                         "denoise": 1.0,
                         "model": ["1", 0], "positive": ["3", 0],
                         "negative": ["2", 0], "latent_image": ["4", 0]}},
        "6": {"class_type": "VAEDecode",
              "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": "comfy_gen", "images": ["6", 0]}},
    }


def merge_style(prompt, negative, style_key):
    """把风格关键词并入正向提示词,把风格干扰项并入负向提示词。"""
    st = STYLES[style_key]
    if st["suffix"]:
        prompt = f"{prompt}, {st['suffix']}" if prompt else st["suffix"]
    if st["negative_add"]:
        extra = [t.strip() for t in st["negative_add"].split(",") if t.strip()]
        have = {t.strip().lower() for t in negative.split(",") if t.strip()}
        for t in extra:
            if t.lower() not in have:
                negative += f", {t}"
                have.add(t.lower())
    return prompt, negative, st


def main():
    global SERVER
    _fix_windows_console()

    ap = argparse.ArgumentParser(
        description="ComfyUI SDXL text2img — AI 辅助多风格绘图",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prompt", "-p", help="正向提示词(内容可中文,风格词由预设叠加)")
    ap.add_argument("--negative", "-n", default=NEG_DEFAULT, help="负向提示词(会与风格排除项合并)")
    ap.add_argument("--style", "-s", default="none", choices=sorted(STYLES),
                    help="风格预设 (默认 none,--list-styles 查看)")
    ap.add_argument("--server", default=SERVER, help="ComfyUI 地址 host:port (默认 127.0.0.1:8188)")
    ap.add_argument("--checkpoint", default="sd_xl_base_1.0.safetensors", help="模型文件名")
    ap.add_argument("--width", type=int, default=None, help="默认取风格建议尺寸")
    ap.add_argument("--height", type=int, default=None)
    ap.add_argument("--steps", type=int, default=28)
    ap.add_argument("--cfg", type=float, default=6.5)
    ap.add_argument("--seed", type=int, default=-1, help="-1 为随机")
    ap.add_argument("--sampler", default="dpmpp_2m")
    ap.add_argument("--scheduler", default="karras")
    ap.add_argument("--out", default=None, help="图片保存目录 (默认脚本目录/../output)")
    ap.add_argument("--timeout", type=int, default=900,
                    help="轮询出图结果的超时秒数 (默认 900,即 15 分钟)")
    ap.add_argument("--list-styles", action="store_true")
    ap.add_argument("--list-checkpoints", action="store_true")
    args = ap.parse_args()
    if args.server.strip().lower().startswith("https://"):
        ap.error("--server 暂不支持 https:ComfyUI 本地服务走 http,"
                 "请写 host:port 形式 (如 127.0.0.1:8188)")
    SERVER = clean_server(args.server)

    if args.list_styles:
        print(f"{'参数取值':<12}{'名称':<8}建议尺寸   说明")
        for k in sorted(STYLES):
            st = STYLES[k]
            print(f"{k:<12}{st['name']:<8}{st['w']}x{st['h']}   {st['desc']}")
        return

    if args.list_checkpoints:
        info = api_or_die("/object_info/CheckpointLoaderSimple", context="获取模型清单")
        node = (info or {}).get("CheckpointLoaderSimple") or {}
        required = (node.get("input") or {}).get("required") or {}
        ckpt_spec = required.get("ckpt_name") or []
        names = ckpt_spec[0] if ckpt_spec else []
        if not names:
            print("[空] 未发现任何 checkpoint;请检查 scripts/extra_models_config.yaml "
                  "的 base_path 是否指向正确的模型目录", file=sys.stderr)
            sys.exit(1)
        for c in names:
            print(c)
        return

    if not args.prompt:
        ap.error("需要 --prompt (或用 --list-styles / --list-checkpoints)")

    # 参数健全性校验:本地给中文提示,不等服务端 400 兜底
    for _name, _val in (("width", args.width), ("height", args.height)):
        if _val is not None and (_val < 64 or _val % 8 != 0):
            ap.error(f"--{_name} {_val} 无效:需 ≥64 且为 8 的倍数 (SDXL 像素对齐要求)")
    if args.steps < 1:
        ap.error(f"--steps {args.steps} 无效:至少为 1")
    if args.cfg <= 0:
        ap.error(f"--cfg {args.cfg} 无效:需大于 0")
    if args.timeout < 1:
        ap.error(f"--timeout {args.timeout} 无效:至少为 1 秒")

    # 检查服务是否在线
    api_or_die("/system_stats", context="连接服务")

    # 合并风格
    prompt, negative, st = merge_style(args.prompt, args.negative, args.style)
    w, h = resolve_size(args.width, args.height, st)
    seed = args.seed if args.seed >= 0 else random.randint(0, 2**48 - 1)

    print(f"[AI 辅助生成] 风格={st['name']}({args.style})  模型={args.checkpoint}")
    wf = build_workflow(prompt, negative, w, h, args.steps, args.cfg,
                        seed, args.sampler, args.scheduler, args.checkpoint)
    r = api_or_die("/prompt", {"prompt": wf, "client_id": CLIENT_ID}, context="提交任务")
    pid = r["prompt_id"]
    print(f"[提交] prompt_id={pid} seed={seed} {w}x{h} steps={args.steps}")

    # 轮询历史
    deadline = time.time() + args.timeout
    outputs = None
    try:
        while time.time() < deadline:
            time.sleep(2)
            try:
                hist = api(f"/history/{pid}")
            except urllib.error.HTTPError as e:
                print(f"[HTTP {e.code}] 查询进度失败:{e.reason}", file=sys.stderr)
                detail = _http_error_detail(e)
                if detail:
                    print(detail, file=sys.stderr)
                _try_interrupt()
                sys.exit(1)
            except urllib.error.URLError as e:
                print("[服务失联] " + _explain_url_error(e), file=sys.stderr)
                print("任务可能仍在服务器上运行,稍后可在 ComfyUI 网页查看结果。", file=sys.stderr)
                _try_interrupt()
                sys.exit(1)
            except socket.timeout:
                # 连接已建立但响应挂起:urllib 在读阶段抛裸 socket.timeout,
                # 不经过 URLError 包装,必须单独接住,否则裸 traceback 崩溃
                print("[服务无响应] 查询进度的请求超时:服务已接受连接但长时间未返回数据。",
                      file=sys.stderr)
                print("任务可能仍在服务器上运行,稍后可在 ComfyUI 网页查看结果。", file=sys.stderr)
                _try_interrupt()
                sys.exit(1)
            if pid in hist:
                status = hist[pid].get("status", {})
                if status.get("status_str") == "error":
                    print("[失败]", json.dumps(status.get("messages", []), ensure_ascii=False)[:2000])
                    _try_interrupt()
                    sys.exit(1)
                if hist[pid].get("outputs"):
                    outputs = hist[pid]["outputs"]
                    break
    except KeyboardInterrupt:
        print("\n[中断] 收到 Ctrl+C,正在通知服务器停止任务…", file=sys.stderr)
        _try_interrupt()
        print("[中断] 已退出;若服务器仍在出图,可到 ComfyUI 网页查看。", file=sys.stderr)
        sys.exit(130)
    if not outputs:
        print(f"[超时] {args.timeout} 秒未完成,正在通知服务器停止任务…", file=sys.stderr)
        _try_interrupt()
        sys.exit(1)

    # 下载图片
    out_dir = os.path.abspath(args.out or os.path.join(os.path.dirname(__file__), "..", "output"))
    os.makedirs(out_dir, exist_ok=True)
    failures = 0
    saved = 0
    for node_out in outputs.values():
        for img in node_out.get("images", []):
            sub = img.get("subfolder", "")
            q = urllib.parse.urlencode({"filename": img["filename"], "subfolder": sub, "type": img.get("type", "output")})
            try:
                with urllib.request.urlopen(f"http://{SERVER}/view?{q}", timeout=60) as resp:
                    data = resp.read()
            except urllib.error.HTTPError as e:
                print(f"[HTTP {e.code}] 下载图片失败:{img['filename']}({e.reason})", file=sys.stderr)
                if e.code == 404:
                    print("图片在服务器上不存在:可能已被清理,或 subfolder/type 与记录不一致。",
                          file=sys.stderr)
                failures += 1
                continue  # 多图输出时逐张容错,不因单张失败放弃其余
            except urllib.error.URLError as e:
                print(_explain_url_error(e), file=sys.stderr)
                failures += 1
                continue
            except socket.timeout:
                # 与轮询同理:读挂起抛裸 socket.timeout,逐张容错不中断
                print(f"[服务无响应] 下载图片超时:{img['filename']}(连接已建立但长时间未返回)",
                      file=sys.stderr)
                failures += 1
                continue
            # 保存路径带 subfolder,避免不同子目录下同名文件互相覆盖
            rel = os.path.join(sub, os.path.basename(img["filename"])) if sub \
                else os.path.basename(img["filename"])
            dst = os.path.normpath(os.path.join(out_dir, rel))
            parent = os.path.dirname(dst)
            if parent:
                os.makedirs(parent, exist_ok=True)
            # 写文件不再额外包装:os.makedirs(exist_ok=True) 已覆盖主要失败面
            with open(dst, "wb") as f:
                f.write(data)
            saved += 1
            print(f"[完成·AI 辅助] {dst}  ({len(data)/1024:.0f} KB)")
    if failures:
        print(f"[失败] {failures} 张图片下载失败,其余图片已尽量保存", file=sys.stderr)
        sys.exit(1)
    if not saved:
        # outputs 存在但没有任何 images 记录:不能静默 exit 0 装作成功
        print("[警告] 任务完成但没有图片落盘:服务器返回的 outputs 中没有可下载的 images 记录。",
              file=sys.stderr)
        print(f"outputs 原文:{json.dumps(outputs, ensure_ascii=False)[:1500]}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
