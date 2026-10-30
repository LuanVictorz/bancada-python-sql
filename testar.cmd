@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONUTF8=1"
python -m unittest discover -s tests -v
exit /b %errorlevel%
