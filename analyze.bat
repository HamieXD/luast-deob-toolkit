@echo off
setlocal
if "%~1"=="" (
  echo Usage: analyze.bat ^<obfuscated.lua^> [constant_table_name]
  exit /b 2
)
set "TABLEARG="
if not "%~2"=="" set "TABLEARG=--table %~2"
py "%~dp0luast_deob.py" analyze "%~1" -o "%~dpn1_analysis" %TABLEARG%
if errorlevel 1 exit /b %errorlevel%
echo.
echo Analysis written to: %~dpn1_analysis
endlocal
