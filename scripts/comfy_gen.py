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
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SERVER = "127.0.0.1:8188"
CLIENT_ID = "zcode_comfy_gen"

NEG_DEFAULT = "text, watermark, low quality, blurry, deformed hands, ugly"

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
    # Windows 控制台中文输出兜底
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(
        description="ComfyUI SDXL text2img — AI 辅助多风格绘图",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prompt", "-p", help="正向提示词(内容可中文,风格词由预设叠加)")
    ap.add_argument("--negative", "-n", default=NEG_DEFAULT, help="负向提示词(会与风格排除项合并)")
    ap.add_argument("--style", "-s", default="none", choices=sorted(STYLES),
                    help="风格预设 (默认 none,--list-styles 查看)")
    ap.add_argument("--checkpoint", default="sd_xl_base_1.0.safetensors", help="模型文件名")
    ap.add_argument("--width", type=int, default=None, help="默认取风格建议尺寸")
    ap.add_argument("--height", type=int, default=None)
    ap.add_argument("--steps", type=int, default=28)
    ap.add_argument("--cfg", type=float, default=6.5)
    ap.add_argument("--seed", type=int, default=-1, help="-1 为随机")
    ap.add_argument("--sampler", default="dpmpp_2m")
    ap.add_argument("--scheduler", default="karras")
    ap.add_argument("--out", default=None, help="图片保存目录 (默认脚本目录/../output)")
    ap.add_argument("--list-styles", action="store_true")
    ap.add_argument("--list-checkpoints", action="store_true")
    args = ap.parse_args()

    if args.list_styles:
        print(f"{'参数取值':<12}{'名称':<8}建议尺寸   说明")
        for k in sorted(STYLES):
            st = STYLES[k]
            print(f"{k:<12}{st['name']:<8}{st['w']}x{st['h']}   {st['desc']}")
        return

    if args.list_checkpoints:
        for c in api("/object_info/CheckpointLoaderSimple")["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]:
            print(c)
        return

    if not args.prompt:
        ap.error("需要 --prompt (或用 --list-styles / --list-checkpoints)")

    # 检查服务是否在线
    api("/system_stats")

    # 合并风格
    prompt, negative, st = merge_style(args.prompt, args.negative, args.style)
    w = args.width or st["w"]
    h = args.height or st["h"]
    seed = args.seed if args.seed >= 0 else random.randint(0, 2**48 - 1)

    print(f"[AI 辅助生成] 风格={st['name']}({args.style})  模型={args.checkpoint}")
    wf = build_workflow(prompt, negative, w, h, args.steps, args.cfg,
                        seed, args.sampler, args.scheduler, args.checkpoint)
    r = api("/prompt", {"prompt": wf, "client_id": CLIENT_ID})
    pid = r["prompt_id"]
    print(f"[提交] prompt_id={pid} seed={seed} {w}x{h} steps={args.steps}")

    # 轮询历史
    deadline = time.time() + 900
    outputs = None
    while time.time() < deadline:
        time.sleep(2)
        hist = api(f"/history/{pid}")
        if pid in hist:
            status = hist[pid].get("status", {})
            if status.get("status_str") == "error":
                print("[失败]", json.dumps(status.get("messages", []), ensure_ascii=False)[:2000])
                sys.exit(1)
            if hist[pid].get("outputs"):
                outputs = hist[pid]["outputs"]
                break
    if not outputs:
        print("[超时] 15 分钟未完成")
        sys.exit(1)

    # 下载图片
    out_dir = os.path.abspath(args.out or os.path.join(os.path.dirname(__file__), "..", "output"))
    os.makedirs(out_dir, exist_ok=True)
    for node_out in outputs.values():
        for img in node_out.get("images", []):
            q = urllib.parse.urlencode({"filename": img["filename"], "subfolder": img.get("subfolder", ""), "type": img.get("type", "output")})
            with urllib.request.urlopen(f"http://{SERVER}/view?{q}", timeout=60) as resp:
                data = resp.read()
            dst = os.path.join(out_dir, os.path.basename(img["filename"]))
            with open(dst, "wb") as f:
                f.write(data)
            print(f"[完成·AI 辅助] {dst}  ({len(data)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
