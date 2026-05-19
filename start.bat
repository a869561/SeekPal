@echo off
setlocal enabledelayedexpansion
title SeekPal - Launcher

echo ============================================
echo   SeekPal - Iniciando entorno
echo ============================================
echo.

REM --- 1. Docker ---
echo [1/5] Comprobando Docker Desktop...
docker info >nul 2>&1
if not errorlevel 1 goto dockerok

echo   Docker no esta corriendo. Abriendo Docker Desktop...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
echo   Esperando a que Docker arranque...
set _tries=0
:waitdocker
timeout /t 3 /nobreak >nul
docker info >nul 2>&1
if not errorlevel 1 goto dockerok
set /a _tries=!_tries!+1
if !_tries! lss 40 goto waitdocker
echo   ERROR: Docker no respondio tras 120s.
pause
exit /b 1

:dockerok
echo   Docker OK.
echo.

REM --- 2. MongoDB ---
echo [2/5] Levantando MongoDB...
pushd "%~dp0"
docker compose up -d mongodb
if errorlevel 1 (
    echo   ERROR levantando MongoDB.
    popd
    pause
    exit /b 1
)
popd
echo   MongoDB OK.
echo.

REM --- 3. Ollama ---
echo [3/5] Comprobando Ollama...
ollama --version >nul 2>&1
if not errorlevel 1 goto ollamafound

echo   Ollama no esta instalado. Intentando winget...
winget --version >nul 2>&1
if errorlevel 1 goto ollamamanual

winget install Ollama.Ollama --accept-source-agreements --accept-package-agreements --silent
if errorlevel 1 goto ollamamanual

for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul ^| findstr /i "PATH"') do set USERPATH=%%B
set "PATH=%PATH%;%USERPATH%"
ollama --version >nul 2>&1
if not errorlevel 1 goto ollamafound

:ollamamanual
echo   Descargando Ollama desde ollama.com...
powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile $env:TEMP\OllamaSetup.exe -UseBasicParsing; Start-Process -Wait -FilePath $env:TEMP\OllamaSetup.exe -ArgumentList '/SILENT' } catch { exit 1 }"
if errorlevel 1 (
    echo   ERROR: no se pudo instalar Ollama automaticamente.
    echo   Instalalo manualmente desde https://ollama.com/download y vuelve a ejecutar.
    pause
    exit /b 1
)
for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul ^| findstr /i "PATH"') do set USERPATH=%%B
set "PATH=%PATH%;%USERPATH%"

:ollamafound
echo   Ollama OK.

tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /I "ollama.exe" >nul
if errorlevel 1 (
    start "" /B ollama serve
    timeout /t 3 /nobreak >nul
)

set "_modelflag=%~dp0backend\.models_pulled"
if exist "%_modelflag%" goto modelsok
echo   Descargando modelos (primera vez, puede tardar varios minutos)...
ollama pull bge-m3
if errorlevel 1 echo   AVISO: fallo descargando bge-m3 (reintenta despues).
ollama pull llama3.2:3b
if errorlevel 1 echo   AVISO: fallo descargando llama3.2:3b (reintenta despues).
echo done > "%_modelflag%"

:modelsok
echo.

REM --- 4. Backend Python ---
echo [4/5] Lanzando backend Python en ventana separada...
start "SeekPal Backend" cmd /k "cd /d %~dp0backend && (if not exist .venv\Scripts\python.exe (python -m venv .venv && .venv\Scripts\python -m pip install -r requirements.txt)) && .venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 3000"

REM --- 5. Frontend ---
echo [5/5] Lanzando frontend en ventana separada...
start "SeekPal Frontend" cmd /k "cd /d %~dp0client && npm run dev"

echo.
echo Listo. Backend en http://localhost:3000  Frontend en http://localhost:5173
echo Documentacion API en http://localhost:3000/docs
echo.
pause
endlocal
