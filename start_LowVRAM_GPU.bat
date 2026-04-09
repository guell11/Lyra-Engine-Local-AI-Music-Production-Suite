@echo off
chcp 65001 >nul 2>&1
title Lyra-Engine (Low VRAM)

echo.
echo  ============================================
echo    Lyra-Engine - MODO LOW VRAM
echo    Ideal para GPUs com 4GB a 8GB de VRAM
echo  ============================================
echo.
echo [AVISO] Esse modo vai usar a RAM normal como backup da sua Placa de Video.
echo.

set LYRA_DEVICE=cuda
set LYRA_VRAM_MODE=ram
set LYRA_GEMMA_LAYERS=5
set LYRA_QUANTIZATION=

call "%~dp0bootstrap_env.bat"
if errorlevel 1 (
    echo.
    pause
    exit /b 1
)

call "%~dp0bootstrap_ollama.bat"
if errorlevel 1 (
    echo.
    pause
    exit /b 1
)

echo [SETUP] Instalando dependencias basicas...
"%LYRA_PIP%" install -q flask huggingface-hub requests >nul 2>&1

taskkill /F /IM ace-server.exe >nul 2>&1

echo [START] Iniciando Lyra-Engine em Low VRAM...
"%LYRA_PYTHON%" app.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERRO] O servidor fechou com erro.
)

echo.
pause
