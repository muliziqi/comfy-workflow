@echo off
rem Keep comments ASCII-only: cmd mis-parses multi-byte REM lines (offset drift).
rem chcp 65001 must run before any non-ASCII echo so Chinese output renders.
rem Delayed expansion is REQUIRED by the extra-args collector below: it lets
rem argument text be read after parsing, so metacharacters inside an argument
rem are never treated as command separators. Side effect: a literal `!` in an
rem argument is dropped (harmless for ComfyUI flags).
chcp 65001 >nul
setlocal enabledelayedexpansion
rem ============================================================
rem Start ComfyUI headless (no desktop window needed).
rem
rem Usage:
rem   start_comfyui.bat                 default port 8188
rem   start_comfyui.bat 8189            custom port
rem   start_comfyui.bat 8188 --lowvram  extra args go AFTER the port
rem                                     and are passed through to main.py
rem
rem Machine setup: edit PY / CWD in the CONFIG section below, then
rem edit base_path in extra_models_config.yaml (same folder).
rem
rem NOTE: this script always loads the yaml sitting NEXT TO ITSELF.
rem       Do not launch stray copies of this script from other/old
rem       copies of this repo, or models may be mounted from the
rem       wrong place.
rem ============================================================

rem ---------------- CONFIG (edit for your machine) ----------------
rem PY: python.exe inside ComfyUI's bundled venv
set "PY=D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"
rem CWD: ComfyUI program folder, must contain main.py
set "CWD=D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI"
rem ----------------------------------------------------------------

rem CFG: always the yaml next to this script (travels with the repo)
set "CFG=%~dp0extra_models_config.yaml"

rem ---- arg 1 must be a numeric port; flag bad input, exit at top level ----
rem (exit /b inside if-blocks does not propagate to `cmd /c`, so the
rem  exit happens at top level after the checks; see git history)
rem Validate WITHOUT `echo %~1|`: a cmd metacharacter in %~1 (say "a&b")
rem would be parsed as a command separator there and abort the script.
rem Instead copy %~1 through a quoted set, then strip every digit 0-9 with
rem set-substitutions; only a pure number strips down to the bare brackets.
rem The [ ] sentinel keeps DIGITS defined through the whole chain: a
rem substitution like %DIGITS:9=% on an UNDEFINED variable leaves literal
rem junk ("9=") and would reject valid ports. The chain must also run at
rem TOP LEVEL (not inside a block), where %DIGITS% refs expand before the
rem chain has run.
set "PORT=8188"
set "PORTARG=%~1"
set "BADPORT="
set "DIGITS=[%PORTARG%]"
set "DIGITS=%DIGITS:0=%"
set "DIGITS=%DIGITS:1=%"
set "DIGITS=%DIGITS:2=%"
set "DIGITS=%DIGITS:3=%"
set "DIGITS=%DIGITS:4=%"
set "DIGITS=%DIGITS:5=%"
set "DIGITS=%DIGITS:6=%"
set "DIGITS=%DIGITS:7=%"
set "DIGITS=%DIGITS:8=%"
set "DIGITS=%DIGITS:9=%"
if defined PORTARG if not "%DIGITS%"=="[]" set "BADPORT=1"
if defined PORTARG if not defined BADPORT set "PORT=%PORTARG%"
if defined BADPORT (
    echo [错误] 第 1 个参数必须是端口号【纯数字】,当前收到:"%~1"
    echo        附加参数如 --lowvram 请写在端口之后,例如:
    echo        start_comfyui.bat 8188 --lowvram
    pause
    exit /b 1
)
title ComfyUI port %PORT%

rem ---- pre-flight checks: PY / CWD / CFG must exist ----
set "MISSING="
if not exist "%PY%" (
    echo [错误] 找不到 Python:"%PY%"
    echo        请编辑本脚本顶部「可配置区」,把 PY 改为本机 ComfyUI venv 的 python.exe
    set "MISSING=1"
)
if not exist "%CWD%\main.py" (
    echo [错误] 找不到 ComfyUI 程序:"%CWD%\main.py"
    echo        请编辑本脚本顶部「可配置区」,把 CWD 改为本机 ComfyUI 程序目录
    set "MISSING=1"
)
if not exist "%CFG%" (
    echo [错误] 找不到模型路径配置:"%CFG%"
    echo        请确认 extra_models_config.yaml 与本脚本在同一目录
    set "MISSING=1"
)
if defined MISSING (
    pause
    exit /b 1
)

rem ---- collect args from #2 on, one arg per shift ----
rem The old `for /f "tokens=1,*" in ("%*")` aborted the whole script (or
rem silently died) when %* carried a cmd metacharacter such as "a&b" or an
rem unbalanced quote. Here each arg is copied through a quoted set into
rem TMPARG, then accumulated with DELAYED expansion and re-quoted, so arg
rem text is never expanded at parse time and can never split a command.
rem Re-adding quotes is transparent to main.py: cmd strips them when it
rem tokenizes the launch line, and values with spaces stay one argument.
rem Known limits: a literal `!` inside an extra arg is dropped by delayed
rem expansion; an arg mixing an embedded quote with a metacharacter still
rem cannot be expressed (cmd itself cannot pass it through intact).
rem leading space in EXTRA is what separates it from %PORT% at launch;
rem no-extra runs leave EXTRA undefined.
set "EXTRA="
:collect_extra
rem Copy the next arg through a quoted set FIRST (absorbs unbalanced
rem quotes into TMPARG), then guard on the VARIABLE. Never test raw %2
rem (`if [%2]==[]` re-parses the arg text and aborts on an unbalanced
rem quote; `if "%~2"==""` is safe because the tilde strips the quotes).
rem Limitation: a literal empty "" argument also reads as empty and ends
rem collection early, dropping any args after it (ComfyUI takes no empty
rem arguments, so this only matters for typos).
set "TMPARG=%~2"
if not defined TMPARG goto after_extra
set "EXTRA=!EXTRA! "!TMPARG!""
shift
goto collect_extra
:after_extra

cd /d "%CWD%"
echo [启动] 端口=%PORT%  模型配置=%CFG%
if defined EXTRA echo [启动] 附加参数:%EXTRA%
"%PY%" main.py --extra-model-paths-config "%CFG%" --port !PORT!!EXTRA!
pause
endlocal
