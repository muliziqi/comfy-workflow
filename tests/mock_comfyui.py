"""最小 ComfyUI API 模拟器,供 tests/test_comfy_gen.py 做端到端冒烟与错误路径测试。

只实现 comfy_gen.py 用到的端点(纯标准库 http.server):
  GET  /system_stats
  GET  /object_info/CheckpointLoaderSimple
  POST /prompt
  GET  /history/<prompt_id>
  GET  /view?filename=...
  POST /interrupt

触发约定(写进正向提示词即可,供测试断言错误路径):
  含 "TRIGGER_400" → /prompt 返回 400 + node_errors(模拟工作流校验失败)
  含 "TRIGGER_404" → 任务正常完成,但 /view 对该图返回 404(模拟成图已丢失)
"""
import json
import re
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MOCK_CKPT = "mock_sdxl_base_1.0.safetensors"

# 1x1 透明 PNG 的完整字节
PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c626001000000ffff03000006000557bfabd400000000"
    "49454e44ae426082")


class MockComfyUIHandler(BaseHTTPRequestHandler):
    server_version = "MockComfyUI/1.0"

    def log_message(self, *args):  # 静默,避免污染测试输出
        pass

    # ---------- helpers ----------
    def _send_json(self, obj, status=200):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _positive_text(self, workflow):
        """取工作流里正向提示词节点(节点 "3")的 text。"""
        node = (workflow or {}).get("3") or {}
        return (node.get("inputs") or {}).get("text") or ""

    # ---------- routes ----------
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/system_stats":
            self._send_json({"system": {"comfyui_version": "mock-0.0.1"},
                             "devices": []})
        elif parsed.path == "/object_info/CheckpointLoaderSimple":
            self._send_json({"CheckpointLoaderSimple": {
                "input": {"required": {"ckpt_name": [[MOCK_CKPT]]}},
                "output": ["MODEL", "CLIP", "VAE"],
                "output_name": ["MODEL", "CLIP", "VAE"],
                "name": "CheckpointLoaderSimple",
                "category": "loaders"}})
        elif parsed.path.startswith("/history/"):
            m = re.match(r"^/history/([^/?]+)", parsed.path)
            pid = m.group(1) if m else None
            job = self.server.jobs.get(pid)
            if not job:
                self._send_json({})
                return
            self._send_json({pid: {
                "status": {"status_str": "success", "completed": True,
                           "messages": []},
                "outputs": {"7": {"images": job["images"]}}}})
        elif parsed.path == "/view":
            q = urllib.parse.parse_qs(parsed.query)
            filename = (q.get("filename") or [""])[0]
            if filename == "missing.png":  # TRIGGER_404 的成图
                self._send_json({"error": "not found"}, 404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(PNG_1PX)))
            self.end_headers()
            self.wfile.write(PNG_1PX)
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/prompt":
            body = self._read_json()
            text = self._positive_text(body.get("prompt"))
            if "TRIGGER_400" in text:
                self._send_json({
                    "error": "prompt_outputs_failed_validation",
                    "node_errors": {
                        "5": {"errors": [{"message": "Mock validation failed",
                                          "details": "", "type": "mock_error"}],
                              "class_type": "KSampler"}}}, 400)
                return
            pid = f"mock-{self.server.job_counter}"
            self.server.job_counter += 1
            if "TRIGGER_404" in text:
                images = [{"filename": "missing.png", "subfolder": "",
                           "type": "output"}]
            elif "TRIGGER_SUB" in text:  # 两个 subfolder 下同名文件
                images = [{"filename": "mock_00001_.png", "subfolder": "sub",
                           "type": "output"},
                          {"filename": "mock_00001_.png", "subfolder": "",
                           "type": "output"}]
            else:
                images = [{"filename": "mock_00001_.png", "subfolder": "",
                           "type": "output"}]
            self.server.jobs[pid] = {"images": images}
            self._send_json({"prompt_id": pid, "number": self.server.job_counter,
                             "node_errors": {}})
        elif parsed.path == "/interrupt":
            self._send_json({})
        else:
            self._send_json({"error": "not found"}, 404)


class MockComfyUI:
    """在 127.0.0.1 随机空闲端口起一个模拟服务;with 语句管理生命周期。"""

    def __init__(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), MockComfyUIHandler)
        self.httpd.jobs = {}
        self.httpd.job_counter = 1
        self.thread = threading.Thread(target=self.httpd.serve_forever,
                                       daemon=True)

    @property
    def port(self):
        return self.httpd.server_address[1]

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()
        return False


if __name__ == "__main__":  # 手动联调:python tests/mock_comfyui.py
    with MockComfyUI() as m:
        print(f"Mock ComfyUI listening on http://127.0.0.1:{m.port} (Ctrl+C 退出)")
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
