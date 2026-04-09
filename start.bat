@echo off
chcp 65001 >nul 2>&1
title Lyra-Engine

echo.
echo  ============================================
echo    Lyra-Engine
echo    Gerador de Musica com IA Local
echo  ============================================
echo.

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

echo [SETUP] Verificando Visual C++ Redistributable...
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" /v Version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [SETUP] VC++ Redistributable nao encontrado. Baixando...
    if not exist "vc_redist.x64.exe" (
        powershell -Command "Invoke-WebRequest -Uri 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile 'vc_redist.x64.exe'" >nul 2>&1
    )
    if exist "vc_redist.x64.exe" (
        echo [SETUP] Instalando VC++ Redistributable...
        start /wait vc_redist.x64.exe /install /quiet /norestart
        echo [SETUP] VC++ Redistributable instalado!
    ) else (
        echo [AVISO] Nao foi possivel baixar VC++ Redistributable.
        echo [AVISO] Baixe manualmente: https://aka.ms/vs/17/release/vc_redist.x64.exe
    )
) else (
    echo [SETUP] VC++ Redistributable OK!
)

echo [SETUP] Instalando dependencias basicas...
"%LYRA_PIP%" install -q flask huggingface-hub requests >nul 2>&1

echo.
echo [START] Iniciando Lyra-Engine...
echo [START] Abra http://localhost:5000 no seu navegador
echo [START] Na primeira vez vai baixar modelos - aguarde.
echo.

taskkill /F /IM ace-server.exe >nul 2>&1

"%LYRA_PYTHON%" app.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERRO] O servidor fechou com erro. Veja a mensagem acima.
)

echo.
pause
