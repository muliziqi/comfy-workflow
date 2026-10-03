"""comfy_gen.py 的单元测试与端到端测试(纯标准库 unittest)。

运行:python -m unittest discover tests -v

--server 清洗的测试方式(两种候选中固定为 monkeypatch 方式,全文件不混用):
  patch sys.argv 后直接调用 comfy_gen.main(),断言 comfy_gen.SERVER
  模块全局被 main() 以清洗后的值覆盖(配合 --list-styles 让 main()
  在联网之前提前返回,全程无网络请求)。
"""
import io
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SCRIPTS = os.path.join(REPO, "scripts")
sys.path.insert(0, SCRIPTS)

import comfy_gen  # noqa: E402
from mock_comfyui import MockComfyUI, MOCK_CKPT  # noqa: E402

PY = sys.executable
COMFY_GEN = os.path.join(SCRIPTS, "comfy_gen.py")
# 防代理环境干扰回环地址请求
ENV = {**os.environ,
       "no_proxy": "127.0.0.1,localhost",
       "NO_PROXY": "127.0.0.1,localhost"}


class MergeStyleTest(unittest.TestCase):
    def test_appends_suffix_and_merges_negative(self):
        p, n, st = comfy_gen.merge_style("一只猫", "low quality", "ink")
        self.assertTrue(p.startswith("一只猫"))
        self.assertIn("ink wash painting", p)
        self.assertIn("low quality", n)
        self.assertIn("color", n)
        self.assertEqual(st["name"], "水墨")

    def test_negative_not_duplicated(self):
        _, n, _ = comfy_gen.merge_style("x", "color, blurry", "ink")
        tokens = [t.strip().lower() for t in n.split(",")]
        self.assertEqual(tokens.count("color"), 1)      # 已有则不重复并入
        self.assertIn("colorful", tokens)               # 风格排除项正常并入

    def test_none_style_keeps_prompt(self):
        p, n, _ = comfy_gen.merge_style("a cat", "low quality", "none")
        self.assertEqual(p, "a cat")
        self.assertEqual(n, "low quality")

    def test_empty_prompt_gets_suffix_only(self):
        p, _, _ = comfy_gen.merge_style("", "", "ink")
        self.assertEqual(p, comfy_gen.STYLES["ink"]["suffix"])

    def test_unknown_style_raises(self):
        with self.assertRaises(KeyError):
            comfy_gen.merge_style("x", "", "no-such-style")


class BuildWorkflowTest(unittest.TestCase):
    def test_node_graph_structure(self):
        wf = comfy_gen.build_workflow("p", "n", 1024, 768, 28, 6.5, 1,
                                      "dpmpp_2m", "karras", "sd_xl.safetensors")
        self.assertEqual(set(wf), {"1", "2", "3", "4", "5", "6", "7"})
        self.assertEqual(wf["1"]["class_type"], "CheckpointLoaderSimple")
        self.assertEqual(wf["1"]["inputs"]["ckpt_name"], "sd_xl.safetensors")
        self.assertEqual(wf["2"]["inputs"]["text"], "n")   # 负向
        self.assertEqual(wf["3"]["inputs"]["text"], "p")   # 正向
        self.assertEqual(wf["4"]["inputs"]["width"], 1024)
        self.assertEqual(wf["4"]["inputs"]["height"], 768)
        self.assertEqual(wf["4"]["inputs"]["batch_size"], 1)

    def test_sampler_links(self):
        wf = comfy_gen.build_workflow("p", "n", 832, 1216, 28, 6.5, 42,
                                      "dpmpp_2m", "karras", "c.safetensors")
        ks = wf["5"]["inputs"]
        self.assertEqual(ks["seed"], 42)
        self.assertEqual(ks["steps"], 28)
        self.assertEqual(ks["cfg"], 6.5)
        self.assertEqual(ks["denoise"], 1.0)
        self.assertEqual(ks["model"], ["1", 0])
        self.assertEqual(ks["positive"], ["3", 0])
        self.assertEqual(ks["negative"], ["2", 0])
        self.assertEqual(ks["latent_image"], ["4", 0])
        self.assertEqual(wf["6"]["inputs"]["samples"], ["5", 0])
        self.assertEqual(wf["6"]["inputs"]["vae"], ["1", 2])
        self.assertEqual(wf["7"]["inputs"]["images"], ["6", 0])


class ResolveSizeTest(unittest.TestCase):
    STYLE = {"w": 832, "h": 1216}

    def test_both_none_uses_style(self):
        self.assertEqual(comfy_gen.resolve_size(None, None, self.STYLE),
                         (832, 1216))

    def test_partial_override(self):
        self.assertEqual(comfy_gen.resolve_size(1024, None, self.STYLE),
                         (1024, 1216))
        self.assertEqual(comfy_gen.resolve_size(None, 512, self.STYLE),
                         (832, 512))

    def test_explicit_zero_wins(self):
        # 0 是显式取值,不再被 or 回退吞掉(改 None 判断的语义)
        self.assertEqual(comfy_gen.resolve_size(0, 0, self.STYLE), (0, 0))


class CleanServerTest(unittest.TestCase):
    def test_strips_http(self):
        self.assertEqual(comfy_gen.clean_server("http://127.0.0.1:8188"),
                         "127.0.0.1:8188")

    def test_strips_https_keeps_case(self):
        self.assertEqual(comfy_gen.clean_server(" HTTPS://Comfy.example:8189/"),
                         "Comfy.example:8189")

    def test_plain_untouched(self):
        self.assertEqual(comfy_gen.clean_server("127.0.0.1:8188"),
                         "127.0.0.1:8188")

    def test_trailing_slash_stripped(self):
        self.assertEqual(comfy_gen.clean_server("127.0.0.1:8188/"),
                         "127.0.0.1:8188")

    def test_empty_falls_back_to_empty(self):
        self.assertEqual(comfy_gen.clean_server(""), "")
        self.assertEqual(comfy_gen.clean_server(None), "")


class ServerArgTest(unittest.TestCase):
    """--server 清洗走真实 main():monkeypatch sys.argv(本文件固定用此方式)。"""

    def tearDown(self):
        comfy_gen.SERVER = "127.0.0.1:8188"  # 恢复模块全局,避免影响其他用例

    def _main(self, *argv):
        with mock.patch.object(sys, "argv", ["comfy_gen.py", *argv]):
            with redirect_stdout(io.StringIO()):
                comfy_gen.main()

    def test_main_cleans_http_prefix(self):
        self._main("--server", "http://127.0.0.1:8189/", "--list-styles")
        self.assertEqual(comfy_gen.SERVER, "127.0.0.1:8189")

    def test_main_default_server(self):
        self._main("--list-styles")
        self.assertEqual(comfy_gen.SERVER, "127.0.0.1:8188")


class EndToEndTest(unittest.TestCase):
    """经 mock 服务走真实入口(subprocess),断言退出码与输出。"""

    @classmethod
    def setUpClass(cls):
        cls._mock_ctx = MockComfyUI()
        cls.mock = cls._mock_ctx.__enter__()
        cls.server = f"127.0.0.1:{cls.mock.port}"

    @classmethod
    def tearDownClass(cls):
        cls._mock_ctx.__exit__(None, None, None)

    def _run(self, *extra, timeout=60):
        return subprocess.run(
            [PY, COMFY_GEN, "--server", self.server, *extra],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, cwd=REPO, env=ENV)

    def test_smoke_generates_image(self):
        with tempfile.TemporaryDirectory() as out:
            r = self._run("--prompt", "一只戴宇航员头盔的橘猫", "--out", out)
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            self.assertIn("[提交]", r.stdout)
            self.assertIn("[完成", r.stdout)
            files = os.listdir(out)
            self.assertEqual(files, ["mock_00001_.png"])
            self.assertGreater(
                os.path.getsize(os.path.join(out, files[0])), 0)

    def test_list_checkpoints(self):
        r = self._run("--list-checkpoints")
        self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
        self.assertIn(MOCK_CKPT, r.stdout)

    def test_prompt_400_shows_node_errors(self):
        r = self._run("--prompt", "TRIGGER_400 bad node")
        self.assertNotEqual(r.returncode, 0)
        combined = r.stdout + r.stderr
        self.assertIn("[HTTP 400]", combined)
        self.assertIn("node_errors", combined)
        self.assertIn("Mock validation failed", combined)

    def test_view_404_readable(self):
        with tempfile.TemporaryDirectory() as out:
            r = self._run("--prompt", "TRIGGER_404 no image", "--out", out)
            self.assertNotEqual(r.returncode, 0)
            combined = r.stdout + r.stderr
            self.assertIn("[HTTP 404]", combined)
            self.assertIn("missing.png", combined)
            self.assertEqual(os.listdir(out), [])  # 不应落盘残缺文件

    def test_multi_image_subfolder_no_overwrite(self):
        # 不同 subfolder 下的同名文件应分目录保存,单张失败不影响其余
        with tempfile.TemporaryDirectory() as out:
            r = self._run("--prompt", "TRIGGER_SUB two images", "--out", out)
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            self.assertTrue(os.path.isfile(os.path.join(out, "mock_00001_.png")))
            self.assertTrue(os.path.isfile(
                os.path.join(out, "sub", "mock_00001_.png")))


class PollHistoryTimeoutTest(unittest.TestCase):
    """轮询 /history 时连接已建立但响应挂起:裸 socket.timeout 不得裸崩,
    应给中文提示、通知服务器中断并以码 1 退出(复现终验的 TimeoutError 场景)。"""

    def test_history_read_hang_exits_with_chinese_message(self):
        with MockComfyUI() as m:
            real_api = comfy_gen.api

            def hanging_history(path, payload=None, timeout=30):
                if path.startswith("/history/"):
                    raise socket.timeout("timed out")  # 读挂起,非 URLError 包装
                return real_api(path, payload, timeout)

            err = io.StringIO()
            with mock.patch.object(comfy_gen, "api", hanging_history):
                with mock.patch.object(
                        sys, "argv", ["comfy_gen.py",
                                      "--server", f"127.0.0.1:{m.port}",
                                      "--prompt", "x"]):
                    with redirect_stderr(err), redirect_stdout(io.StringIO()):
                        with self.assertRaises(SystemExit) as cm:
                            comfy_gen.main()
        self.assertEqual(cm.exception.code, 1)
        combined = err.getvalue()
        self.assertIn("无响应", combined)          # 中文超时提示
        self.assertNotIn("Traceback", combined)   # 不允许裸堆栈


class HistoryWithoutImagesTest(unittest.TestCase):
    """任务完成但 outputs 节点缺 images 字段:不得静默 exit 0。"""

    def test_outputs_without_images_warns_and_exits_1(self):
        with MockComfyUI() as m:
            real_api = comfy_gen.api

            def strip_images(path, payload=None, timeout=30):
                r = real_api(path, payload, timeout)
                if path.startswith("/history/"):
                    for v in r.values():
                        for node in (v.get("outputs") or {}).values():
                            node.pop("images", None)
                return r

            with tempfile.TemporaryDirectory() as out:
                err = io.StringIO()
                with mock.patch.object(comfy_gen, "api", strip_images):
                    with mock.patch.object(
                            sys, "argv", ["comfy_gen.py",
                                          "--server", f"127.0.0.1:{m.port}",
                                          "--prompt", "x", "--out", out]):
                        with redirect_stderr(err), redirect_stdout(io.StringIO()):
                            with self.assertRaises(SystemExit) as cm:
                                comfy_gen.main()
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("没有图片落盘", err.getvalue())
        # 该路径在 makedirs 之前就退出,输出目录不应存在或应为空
        self.assertFalse(os.path.isdir(out) and os.listdir(out))


class ArgValidationTest(unittest.TestCase):
    """出图参数本地校验与 --server 拒绝:中文提示 + SystemExit,不发网络请求。"""

    def _expect_exit(self, *argv, needle):
        err = io.StringIO()
        with mock.patch.object(sys, "argv", ["comfy_gen.py", *argv]):
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    comfy_gen.main()
        self.assertIn(needle, err.getvalue())
        return cm

    def test_width_needs_multiple_of_8(self):
        cm = self._expect_exit("--prompt", "x", "--width", "100",
                               needle="8 的倍数")
        self.assertEqual(cm.exception.code, 2)

    def test_height_needs_at_least_64(self):
        self._expect_exit("--prompt", "x", "--height", "0", needle="无效")

    def test_steps_needs_positive(self):
        self._expect_exit("--prompt", "x", "--steps", "0", needle="至少为 1")

    def test_cfg_needs_positive(self):
        self._expect_exit("--prompt", "x", "--cfg", "-1", needle="大于 0")

    def test_timeout_needs_at_least_1_second(self):
        self._expect_exit("--prompt", "x", "--timeout", "0",
                          needle="至少为 1 秒")

    def test_https_server_rejected(self):
        self._expect_exit("--prompt", "x", "--server", "https://example.com:8188",
                           needle="不支持 https")

    def test_help_lists_timeout(self):
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["comfy_gen.py", "--help"]):
            with redirect_stdout(out):
                with self.assertRaises(SystemExit):
                    comfy_gen.main()
        self.assertIn("--timeout", out.getvalue())


class OfflineTest(unittest.TestCase):
    """不依赖 mock 服务:离线/错地址时中文提示 + 非零退出。"""

    def _run(self, *argv):
        return subprocess.run(
            [PY, COMFY_GEN, *argv],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, cwd=REPO, env=ENV)

    def test_connection_refused_hints_start_bat(self):
        r = self._run("--prompt", "x", "--server", "127.0.0.1:9")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("start_comfyui.bat", r.stdout + r.stderr)

    def test_bad_host_hints_server_format(self):
        r = self._run("--prompt", "x", "--server", "no-such-host.invalid:8188")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("host:port", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
