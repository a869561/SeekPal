@echo off
setlocal enabledelayedexpansion
title SeekPal Launcher
cls

echo.
echo  ==========================================
echo   SeekPal
echo  ==========================================
echo.

REM ---- Cerrar instancias previas ----
echo  Cerrando instancias anteriores...
taskkill /FI "WINDOWTITLE eq SeekPal Backend" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq SeekPal Frontend" /T /F >nul 2>&1
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr ":3000 " ^| findstr "LISTENING"') do (
    if not "%%P"=="0" taskkill /F /PID %%P /T >nul 2>&1
)
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr ":5173 " ^| findstr "LISTENING"') do (
    if not "%%P"=="0" taskkill /F /PID %%P /T >nul 2>&1
)
for /r "%~dp0backend\qdrant_data" %%f in (*.lock) do del /f "%%f" >nul 2>&1
timeout /t 2 /nobreak >nul

REM ---- Docker ----
<nul set /p "_=  [1/4] Docker..."
docker info >nul 2>&1
if not errorlevel 1 (
    echo  OK
    goto dockerok
)
echo.
echo       Abriendo Docker Desktop...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
set _t=0
:waitdocker
timeout /t 3 /nobreak >nul
docker info >nul 2>&1
if not errorlevel 1 (echo  [1/4] Docker... OK & goto dockerok)
set /a _t=!_t!+1
if !_t! lss 40 goto waitdocker
echo  ERROR: Docker no respondio. Arrancalo manualmente y reintenta.
pause & exit /b 1
:dockerok

REM ---- MongoDB ----
<nul set /p "_=  [2/4] MongoDB..."
pushd "%~dp0"
docker compose up -d mongodb >nul 2>&1
popd
echo  OK

REM ---- Ollama ----
<nul set /p "_=  [3/4] Ollama..."
ollama --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo       Instalando Ollama...
    winget install Ollama.Ollama --accept-source-agreements --accept-package-agreements --silent >nul 2>&1
    <nul set /p "_=  [3/4] Ollama..."
)
tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /I "ollama.exe" >nul
if errorlevel 1 (
    start "" /B ollama serve >nul 2>&1
    timeout /t 3 /nobreak >nul
)
set "_flag=%~dp0backend\.models_pulled"
if not exist "%_flag%" (
    echo.
    echo       Descargando modelos ^(primera vez, varios minutos^)...
    ollama pull bge-m3 >nul 2>&1
    ollama pull llama3.2:3b >nul 2>&1
    echo done > "%_flag%"
    <nul set /p "_=  [3/4] Ollama..."
)
echo  OK

REM ---- Backend y Frontend ----
<nul set /p "_=  [4/4] Backend y Frontend..."
start "SeekPal Backend" cmd /k "cd /d "%~dp0backend" && .venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 3000 --log-level warning"
timeout /t 2 /nobreak >nul
start "SeekPal Frontend" cmd /k "cd /d "%~dp0client" && npm run dev"
echo  OK

echo.
echo  ==========================================
echo   Listo
echo   Frontend  http://localhost:5173
echo   Backend   http://localhost:3000
echo   API docs  http://localhost:3000/docs
echo  ==========================================
echo.
echo  Pulsa cualquier tecla para cerrar esta ventana.
pause >nul
endlocal
exit
