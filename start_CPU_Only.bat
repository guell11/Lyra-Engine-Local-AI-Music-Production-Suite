@echo off
chcp 65001 >nul 2>&1
title Lyra-Engine (Modo CPU Lento)

echo.
echo  ============================================
echo    Lyra-Engine - MODO CPU ONLY
echo    Geracao puramente no Processador
echo  ============================================
echo.
echo [AVISO] O modo CPU demora significativamente mais (horas para musicas)
echo         mas funciona em qualquer computador sem placa de video!
echo.

set LYRA_DEVICE=cpu
set LYRA_VRAM_MODE=ram
set LYRA_GEMMA_LAYERS=0
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

echo [START] Iniciando Lyra-Engine no modo CPU...
"%LYRA_PYTHON%" app.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERRO] O servidor fechou com erro.
)

echo.
pause
