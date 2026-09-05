@echo off
rem 启动 ComfyUI 服务(无头模式,不依赖桌面版窗口)
rem 浏览器访问: http://127.0.0.1:8188
chcp 65001 >nul
set PY=D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe
set CWD=D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI
set CFG=C:\Users\muliz\.zcode\workspace\default\comfy-workflow\scripts\extra_models_config.yaml

cd /d %CWD%
"%PY%" main.py --extra-model-paths-config "%CFG%" --port 8188
pause
