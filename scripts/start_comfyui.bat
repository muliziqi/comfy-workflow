@echo off
rem 启动 ComfyUI 服务(无头模式,不依赖桌面版窗口)
rem 用法: start_comfyui.bat [端口]  (默认 8188;与桌面版冲突时改用 8189)
rem 浏览器访问: http://127.0.0.1:8188
chcp 65001 >nul
title ComfyUI (port %1)
set PY=D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe
set CWD=D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI
set CFG=C:\Users\muliz\.zcode\workspace\default\comfy-workflow\scripts\extra_models_config.yaml
if "%1"=="" (set PORT=8188) else (set PORT=%1)

cd /d %CWD%
"%PY%" main.py --extra-model-paths-config "%CFG%" --port %PORT%
pause
