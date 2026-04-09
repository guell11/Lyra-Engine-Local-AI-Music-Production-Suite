@echo off
setlocal

set "BOOTSTRAP_PY="
where py >nul 2>&1
if not errorlevel 1 (
    py -3.12 -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        set "BOOTSTRAP_PY=py -3.12"
    ) else (
        py -3.11 -c "import sys" >nul 2>&1
        if not errorlevel 1 set "BOOTSTRAP_PY=py -3.11"
    )
)

if not defined BOOTSTRAP_PY (
    where python >nul 2>&1
    if not errorlevel 1 set "BOOTSTRAP_PY=python"
)

if not defined BOOTSTRAP_PY (
    if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "BOOTSTRAP_PY=%LocalAppData%\Programs\Python\Python312\python.exe"
)

if not defined BOOTSTRAP_PY (
    if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "BOOTSTRAP_PY=%LocalAppData%\Programs\Python\Python311\python.exe"
)

if not defined BOOTSTRAP_PY (
    if exist "%LocalAppData%\Microsoft\WindowsApps\python3.12.exe" set "BOOTSTRAP_PY=%LocalAppData%\Microsoft\WindowsApps\python3.12.exe"
)

if not defined BOOTSTRAP_PY (
    if exist "%LocalAppData%\Microsoft\WindowsApps\python.exe" set "BOOTSTRAP_PY=%LocalAppData%\Microsoft\WindowsApps\python.exe"
)

if not defined BOOTSTRAP_PY (
    echo [ERRO] Python 3.11+ nao foi encontrado no PATH.
    endlocal & exit /b 1
)

if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" -c "import sys" >nul 2>&1
    if errorlevel 1 (
        echo [SETUP] Ambiente virtual corrompido. Recriando...
        rmdir /s /q "venv"
    )
)

if not exist "venv\Scripts\python.exe" (
    echo [SETUP] Criando ambiente virtual local...
    call %BOOTSTRAP_PY% -m venv "venv"
    if errorlevel 1 (
        echo [ERRO] Falha ao criar o ambiente virtual.
        endlocal & exit /b 1
    )
)

set "LYRA_PYTHON=%CD%\venv\Scripts\python.exe"
set "LYRA_PIP=%CD%\venv\Scripts\pip.exe"

"%LYRA_PYTHON%" -m pip install -q --upgrade pip setuptools wheel >nul 2>&1

endlocal & (
    set "LYRA_PYTHON=%CD%\venv\Scripts\python.exe"
    set "LYRA_PIP=%CD%\venv\Scripts\pip.exe"
    set "PIP_DISABLE_PIP_VERSION_CHECK=1"
    set "PYTHONUTF8=1"
)
exit /b 0
