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

REM Variables de entorno que suprimen advertencias innecesarias
set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"
set "PYTHONIOENCODING=utf-8"

REM ---- [1/7] Python + dependencias ----
<nul set /p "_=  [1/7] Python..."
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo.
    echo  ERROR: Python no encontrado.
    echo  Instala Python 3.11 o superior desde https://python.org
    echo  Asegurate de marcar "Add Python to PATH" durante la instalacion.
    echo.
    pause & exit /b 1
)
set "_backdir=%~dp0backend"
set "_py=%_backdir%\.venv\Scripts\python.exe"
set "_pip=%_backdir%\.venv\Scripts\pip.exe"
if not exist "%_py%" (
    echo.
    echo       Creando entorno virtual...
    python -m venv "%_backdir%\.venv"
    echo       Instalando dependencias ^(primera vez, puede tardar unos minutos^)...
    "%_pip%" install --upgrade pip --quiet
    "%_pip%" install -r "%_backdir%\requirements.txt" --quiet --prefer-binary
    <nul set /p "_=  [1/7] Python..."
) else (
    "%_pip%" install -r "%_backdir%\requirements.txt" --quiet --prefer-binary
)
echo  OK

REM ---- [2/7] Node.js + dependencias frontend ----
<nul set /p "_=  [2/7] Node.js..."
node --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo.
    echo  ERROR: Node.js no encontrado.
    echo  Instala Node.js 18 o superior desde https://nodejs.org
    echo.
    pause & exit /b 1
)
set "_frontdir=%~dp0client"
if not exist "%_frontdir%\node_modules" (
    echo.
    echo       Instalando dependencias del cliente ^(primera vez^)...
    pushd "%_frontdir%"
    npm install --silent 2>nul
    popd
    <nul set /p "_=  [2/7] Node.js..."
)
echo  OK

REM ---- [3/7] Docker ----
<nul set /p "_=  [3/7] Docker..."
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
if not errorlevel 1 (echo  [3/7] Docker... OK & goto dockerok)
set /a _t=!_t!+1
if !_t! lss 40 goto waitdocker
echo  ERROR: Docker no respondio. Arrancalo manualmente y reintenta.
pause & exit /b 1
:dockerok

REM ---- [4/7] MongoDB ----
<nul set /p "_=  [4/7] MongoDB..."
pushd "%~dp0"
docker compose up -d mongodb >nul 2>&1
popd
echo  OK

REM ---- [5/7] Ollama + modelo de IA ----
<nul set /p "_=  [5/7] Ollama..."
ollama --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo       Instalando Ollama...
    winget install Ollama.Ollama --accept-source-agreements --accept-package-agreements --silent >nul 2>&1
    <nul set /p "_=  [5/7] Ollama..."
)
powershell -noprofile -c "try{Invoke-WebRequest http://localhost:11434/api/version -UseBasicParsing|Out-Null;exit 0}catch{exit 1}" >nul 2>&1
if errorlevel 1 (
    start "" /B ollama serve >nul 2>&1
    timeout /t 5 /nobreak >nul
)
set "_flag=%~dp0backend\.models_pulled_v3"
if not exist "%_flag%" (
    echo.
    echo       Descargando modelo de IA ^(primera vez, varios minutos^)...
    ollama pull qwen3:4b
    echo done > "%_flag%"
    <nul set /p "_=  [5/7] Ollama..."
)
echo  OK

REM ---- [6/7] Aceleracion GPU + modelos de busqueda ----
<nul set /p "_=  [6/7] Preparando IA..."
set "_gpu_setup=%temp%\seekpal_gpu_%random%.ps1"

(
    echo $pip = '%_pip%'
    echo $gpuNames = try { ^(Get-WmiObject Win32_VideoController^).Name -join '^|' } catch { '' }
    echo $hasNVIDIA   = $gpuNames -imatch 'NVIDIA'
    echo $hasAMDdedic = $gpuNames -imatch 'Radeon RX^|Radeon Pro^|Radeon HD'
    echo $hasAMDiGPU  = $gpuNames -imatch 'Radeon Graphics^|Radeon Vega'
    echo $hasIntelArc = $gpuNames -imatch 'Intel Arc'
    echo $hasIntelIGPU= $gpuNames -imatch 'Intel UHD^|Intel HD^|Intel Iris'
    echo if ^($hasNVIDIA^) {
    echo     $vram = try { ^(Get-WmiObject Win32_VideoController ^| Where-Object { $_.Name -imatch 'NVIDIA' } ^| Measure-Object AdapterRAM -Maximum^).Maximum } catch { 0 }
    echo     if ^($vram -ge 2147483648^) {
    echo         $h = ^(^& $pip show onnxruntime-gpu 2^>$null^) -ne $null
    echo         if ^(-not $h^) { Write-Host '  Instalando aceleracion NVIDIA...'; ^& $pip install onnxruntime-gpu --quiet 2^>^&1 ^| Out-Null }
    echo     } else { Write-Host '  Graficos NVIDIA con poca VRAM, usando procesador.' }
    echo } elseif ^($hasAMDdedic -or $hasIntelArc -or $hasAMDiGPU -or $hasIntelIGPU^) {
    echo     $h = ^(^& $pip show onnxruntime-directml 2^>$null^) -ne $null
    echo     if ^(-not $h^) { Write-Host '  Instalando aceleracion AMD/Intel...'; ^& $pip install onnxruntime-directml --quiet 2^>^&1 ^| Out-Null }
    echo } else { Write-Host '  Sin graficos dedicados, usando procesador.' }
) > "%_gpu_setup%"
powershell -noprofile -ExecutionPolicy Bypass -File "%_gpu_setup%" 2>nul
del "%_gpu_setup%" >nul 2>&1

REM Pre-descargar modelos de busqueda si es la primera vez (~2.4 GB)
set "_emb_flag=%~dp0backend\.models_embedding_ready"
if not exist "%_emb_flag%" (
    echo.
    echo       Descargando modelos de busqueda ^(primera vez, ~2 GB, varios minutos^)...
    "%_py%" -W ignore -c "from fastembed import TextEmbedding, SparseTextEmbedding; TextEmbedding(model_name='intfloat/multilingual-e5-large'); SparseTextEmbedding(model_name='Qdrant/bm25'); print('  Modelos listos')"
    echo done > "%_emb_flag%"
    <nul set /p "_=  [6/7] Preparando IA..."
)
echo  OK

REM ---- [7/7] Backend + Frontend ----
<nul set /p "_=  [7/7] Iniciando..."

REM Backend: PowerShell loop — exit code 99 = reiniciar (aplica cambios de configuracion)
start "SeekPal Backend" powershell -noexit -noprofile -ExecutionPolicy Bypass -Command "$host.UI.RawUI.WindowTitle = 'SeekPal Backend'; $env:HF_HUB_DISABLE_SYMLINKS_WARNING='1'; $env:PYTHONIOENCODING='utf-8'; Set-Location '%_backdir%'; while ($true) { & '%_py%' -m uvicorn app.main:app --host 0.0.0.0 --port 3000 --log-level warning; if ($LASTEXITCODE -ne 99) { break }; Write-Host '[SeekPal] Aplicando cambios...' -ForegroundColor Cyan; Start-Sleep 1 }"

timeout /t 2 /nobreak >nul
start "SeekPal Frontend" cmd /k "cd /d "%_frontdir%" && npm run dev"
echo  OK

echo.
echo  ==========================================
echo   Listo
echo   Frontend  http://localhost:5173
echo   Backend   http://localhost:3000
echo  ==========================================
echo.
echo  Pulsa cualquier tecla para cerrar esta ventana.
pause >nul
endlocal
exit
