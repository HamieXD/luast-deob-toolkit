@echo off
setlocal
if "%~1"=="" (
  echo Usage: oneclick.bat "C:\path\to\obfuscated.lua"
  exit /b 2
)
set "INPUT=%~1"
set "OUT=%~dpn1_analysis"
python "%~dp0luast_deob.py" analyze "%INPUT%" -o "%OUT%"
if errorlevel 1 exit /b %errorlevel%
echo.
echo DONE.
echo Send these to ChatGPT:
echo   1. %OUT%\AI_HANDOFF.md
echo   2. the original obfuscated source
echo After Codex runtime probing, also send:
echo   3. RUNTIME_BRIDGE_REPORT.txt
endlocal
