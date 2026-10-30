@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONUTF8=1"
python --version >nul 2>&1
if errorlevel 1 (
    echo Instale Python 3.11 ou superior com a opcao Add python.exe to PATH.
    pause
    exit /b 1
)
python main.py %*
if errorlevel 1 (
    echo A aplicacao nao iniciou. Confira a mensagem acima.
    pause
    exit /b 1
)
