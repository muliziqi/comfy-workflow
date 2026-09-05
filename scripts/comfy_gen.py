#!/usr/bin/env python3
"""ComfyUI API 出图脚本 (SDXL 文生图)。

用法:
  python comfy_gen.py --prompt "一只戴宇航员头盔的橘猫, 电影感" 
  python comfy_gen.py --prompt "..." --width 1024 --height 768 --steps 30 --seed 42
  python comfy_gen.py --list-checkpoints

依赖: 仅 Python 3 标准库。
"""
import argparse
import json
import random
import sys
import time
import urllib.parse
import urllib.request

SERVER = "127.0.0.1:8188"
CLIENT_ID = "zcode_comfy_gen"

NEG_DEFAULT = "text, watermark, low quality, blurry, deformed hands, ugly"


def api(path, payload=None, timeout=30):
    url = f"http://{SERVER}{path}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    else:
        req = url
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def build_workflow(p, neg, w, h, steps, cfg, seed, sampler, scheduler):
    """SDXL 文生图最小工作流 (API 格式)。"""
    return {
        "1": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": p}},
        "2": {"class_type": "CLIPTextEncode",
              "inputs": {"text": neg, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode",
              "inputs": {"text": args.prompt, "clip": ["1", 1]}},
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


def main():
    global args
    ap = argparse.ArgumentParser(description="ComfyUI SDXL text2img")
    ap.add_argument("--prompt", "-p", help="正向提示词")
    ap.add_argument("--negative", "-n", default=NEG_DEFAULT, help="负向提示词")
    ap.add_argument("--checkpoint", default="sd_xl_base_1.0.safetensors", help="模型文件名")
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--height", type=int, default=1024)
    ap.add_argument("--steps", type=int, default=28)
    ap.add_argument("--cfg", type=float, default=6.5)
    ap.add_argument("--seed", type=int, default=-1, help="-1 为随机")
    ap.add_argument("--sampler", default="dpmpp_2m")
    ap.add_argument("--scheduler", default="karras")
    ap.add_argument("--out", default=None, help="图片保存目录 (默认脚本目录/output)")
    ap.add_argument("--list-checkpoints", action="store_true")
    args = ap.parse_args()

    try:
        if args.list_checkpoints:
            for c in api("/object_info/CheckpointLoaderSimple")["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]:
                print(c)
            return

        if not args.prompt:
            ap.error("需要 --prompt (或用 --list-checkpoints)")

        # 检查服务是否在线
        api("/system_stats")

        seed = args.seed if args.seed >= 0 else random.randint(0, 2**48 - 1)
        wf = build_workflow(args.checkpoint, args.negative, args.width, args.height,
                            args.steps, args.cfg, seed, args.sampler, args.scheduler)
        r = api("/prompt", {"prompt": wf, "client_id": CLIENT_ID})
        pid = r["prompt_id"]
        print(f"[提交] prompt_id={pid} seed={seed} {args.width}x{args.height} steps={args.steps}")

        # 轮询历史
        deadline = time.time() + 900
        outputs = None
        while time.time() < deadline:
            time.sleep(2)
            hist = api(f"/history/{pid}")
            if pid in hist:
                st = hist[pid].get("status", {})
                if st.get("status_str") == "error":
                    print("[失败]", json.dumps(st.get("messages", []), ensure_ascii=False)[:2000])
                    sys.exit(1)
                if hist[pid].get("outputs"):
                    outputs = hist[pid]["outputs"]
                    break
        if not outputs:
            print("[超时] 15 分钟未完成")
            sys.exit(1)

        # 下载图片
        import os
        out_dir = os.path.abspath(args.out or os.path.join(os.path.dirname(__file__), "..", "output"))
        os.makedirs(out_dir, exist_ok=True)
        for node_out in outputs.values():
            for img in node_out.get("images", []):
                q = urllib.parse.urlencode({"filename": img["filename"], "subfolder": img.get("subfolder", ""), "type": img.get("type", "output")})
                path = f"/view?{q}"
                with urllib.request.urlopen(f"http://{SERVER}{path}", timeout=60) as resp:
                    data = resp.read()
                dst = os.path.join(out_dir, os.path.basename(img["filename"]))
                with open(dst, "wb") as f:
                    f.write(data)
                print(f"[完成] {dst}  ({len(data)/1024:.0f} KB)")
    except urllib.error.URLError as e:
        print(f"[错误] 无法连接 ComfyUI ({SERVER}): {e.reason}")
        print("请先启动服务: comfy-workflow\\scripts\\start_comfyui.bat")
        sys.exit(1)


if __name__ == "__main__":
    main()
