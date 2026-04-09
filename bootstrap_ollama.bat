@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "OLLAMA_EXE=%LocalAppData%\Programs\Ollama\ollama.exe"
set "OLLAMA_INSTALLER=%TEMP%\OllamaSetup.exe"
set "OLLAMA_LOG=%TEMP%\Lyra_Ollama_Install.log"
set "WAIT_SECONDS=0"

call :find_ollama
if defined OLLAMA_EXE goto have_ollama

echo [SETUP] Ollama nao encontrado. Instalando automaticamente...
echo [SETUP] Log da instalacao: %OLLAMA_LOG%
del /q "%OLLAMA_LOG%" >nul 2>&1

where winget >nul 2>&1
if not errorlevel 1 (
    echo [SETUP] Tentando instalar via winget...
    start "" /B cmd /c winget install -e --id Ollama.Ollama --accept-package-agreements --accept-source-agreements --disable-interactivity --silent >> "%OLLAMA_LOG%" 2>&1
    call :wait_for_process "winget.exe" "AppInstallerCLI.exe" "Instalando Ollama via winget"
    call :find_ollama
    if defined OLLAMA_EXE goto have_ollama
    echo [AVISO] Winget nao concluiu a instalacao do Ollama. Vou tentar o instalador direto.
)

echo [SETUP] Baixando instalador do Ollama...
powershell -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile $env:TEMP\\OllamaSetup.exe; exit 0 } catch { $_ | Out-File -FilePath $env:TEMP\\Lyra_Ollama_Install.log -Append; exit 1 }"
if errorlevel 1 (
    echo [ERRO] Falha ao baixar o instalador do Ollama.
    echo [ERRO] Veja o log em: %OLLAMA_LOG%
    endlocal & exit /b 1
)

if not exist "%OLLAMA_INSTALLER%" (
    echo [ERRO] O instalador do Ollama nao apareceu em %OLLAMA_INSTALLER%.
    endlocal & exit /b 1
)

echo [SETUP] Instalando Ollama pelo instalador direto...
start "" /B "%OLLAMA_INSTALLER%" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART >> "%OLLAMA_LOG%" 2>&1
call :wait_for_process "OllamaSetup.exe" "" "Instalando Ollama pelo setup"
call :find_ollama
if defined OLLAMA_EXE goto have_ollama

echo [SETUP] Tentando modo alternativo do instalador...
start "" /B "%OLLAMA_INSTALLER%" /S >> "%OLLAMA_LOG%" 2>&1
call :wait_for_process "OllamaSetup.exe" "" "Instalando Ollama pelo setup alternativo"
call :find_ollama
if defined OLLAMA_EXE goto have_ollama

echo [ERRO] Nao foi possivel instalar o Ollama automaticamente.
echo [ERRO] Abra manualmente: https://ollama.com/download/windows
echo [ERRO] Log salvo em: %OLLAMA_LOG%
endlocal & exit /b 1

:have_ollama
echo [SETUP] Ollama encontrado: %OLLAMA_EXE%

powershell -ExecutionPolicy Bypass -Command "try { Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Iniciando servico local do Ollama...
    start "" /B "%OLLAMA_EXE%" serve
    call :wait_for_ollama
    if errorlevel 1 (
        echo [AVISO] O Ollama ainda nao respondeu na porta 11434.
        echo [AVISO] O backend ainda vai tentar subir ele sozinho quando necessario.
    ) else (
        echo [SETUP] Ollama online em http://127.0.0.1:11434
    )
) else (
    echo [SETUP] Ollama ja estava online.
)

endlocal & (
    set "OLLAMA_HOST=http://127.0.0.1:11434"
    set "OLLAMA_EXE=%OLLAMA_EXE%"
)
exit /b 0

:find_ollama
set "OLLAMA_EXE="
if exist "%LocalAppData%\Programs\Ollama\ollama.exe" (
    set "OLLAMA_EXE=%LocalAppData%\Programs\Ollama\ollama.exe"
    exit /b 0
)
where ollama >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%I in ('where ollama') do (
        set "OLLAMA_EXE=%%I"
        exit /b 0
    )
)
exit /b 0

:wait_for_process
set "PROC1=%~1"
set "PROC2=%~2"
set "LABEL=%~3"
set "WAIT_SECONDS=0"

:wait_loop
set "RUNNING="
if defined PROC1 (
    tasklist /FI "IMAGENAME eq %PROC1%" | find /I "%PROC1%" >nul 2>&1 && set "RUNNING=1"
)
if not defined RUNNING if defined PROC2 (
    tasklist /FI "IMAGENAME eq %PROC2%" | find /I "%PROC2%" >nul 2>&1 && set "RUNNING=1"
)
if not defined RUNNING exit /b 0

timeout /t 5 >nul
set /a WAIT_SECONDS+=5
echo [SETUP] %LABEL%... aguardando %WAIT_SECONDS%s
if %WAIT_SECONDS% GEQ 180 (
    echo [AVISO] Essa etapa esta demorando bastante.
    echo [AVISO] Se quiser acompanhar, abra: %OLLAMA_LOG%
)
goto wait_loop

:wait_for_ollama
set "WAIT_SECONDS=0"
:wait_ollama_loop
powershell -ExecutionPolicy Bypass -Command "try { Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 exit /b 0
timeout /t 2 >nul
set /a WAIT_SECONDS+=2
echo [SETUP] Aguardando Ollama responder na API... %WAIT_SECONDS%s
if %WAIT_SECONDS% GEQ 30 exit /b 1
goto wait_ollama_loop
