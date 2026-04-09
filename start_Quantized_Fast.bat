@echo off
chcp 65001 >nul 2>&1
title Lyra-Engine (Quantizacao INT8)

echo.
echo  ============================================
echo    Lyra-Engine - MODO MISTO (INT8 Quantizado)
echo    Otimizado para maximo de velocidade com menor VRAM!
echo  ============================================
echo.

set LYRA_DEVICE=cuda
set LYRA_VRAM_MODE=auto
set LYRA_GEMMA_LAYERS=10
set LYRA_QUANTIZATION=int8

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

echo [START] Iniciando Lyra-Engine com Quantizacao...
"%LYRA_PYTHON%" app.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERRO] O servidor fechou com erro.
)

echo.
pause
