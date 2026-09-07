@echo off
REM AirStat India - one-command pipeline (Windows): replay data -> seed -> index ->
REM backtest -> tests -> API -> dashboard.
REM
REM Usage:
REM   make.bat              full pipeline (generates replay data if missing, seeds, starts servers)
REM   make.bat --keep       re-seed without dropping tables
REM   make.bat --serve      skip pipeline, just start both servers
REM   make.bat --stop       stop servers started by this script
REM   make.bat --test       run backend tests only
REM   make.bat --fresh-data force regeneration of the replay dataset
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
set "API_PORT=8000"
set "UI_PORT=5173"
set "RUN_DIR=%TEMP%\airstat"
if not exist "%RUN_DIR%" mkdir "%RUN_DIR%"

echo [make] AirStat India pipeline

if "%~1"=="--stop" goto :stop
if "%~1"=="--test" goto :test
if "%~1"=="--serve" goto :serve

REM ---- 1. environment ----
if not exist "%PY%" (
    echo [make] creating Python venv
    python -m venv .venv || goto :fail
    "%PY%" -m pip install --quiet -r requirements.txt || goto :fail
)

REM ---- 2. replay dataset ----
if "%~1"=="--fresh-data" if exist data\fixtures\replay_quotes.jsonl del data\fixtures\replay_quotes.jsonl
if exist data\fixtures\replay_quotes.jsonl (
    echo [make] replay dataset present - skipping generation ^(use --fresh-data to force^)
) else (
    echo [make] generating replay dataset ^(seed 26056^)
    "%PY%" scripts\generate_replay_data.py || goto :fail
)

REM ---- 3. seed + index + backtest ----
echo [make] seeding database and running pipeline
"%PY%" scripts\seed.py %* || goto :fail

:test
REM ---- 4. tests ----
echo [make] running backend tests
"%PY%" -m pytest backend\tests -q || goto :fail
if "%~1"=="--test" exit /b 0

:serve
REM ---- 5. servers ----
call :stop_quiet

echo [make] starting API on :%API_PORT%
start /b "" cmd /c ""%PY%" -m uvicorn backend.app.main:app --port %API_PORT% > "%RUN_DIR%\api.log" 2>&1"
timeout /t 2 /nobreak >nul
call :wait_api
if errorlevel 1 goto :fail

if not exist frontend\node_modules (
    echo [make] installing frontend dependencies ^(first run^)
    pushd frontend && call npm install || goto :fail_popd
    popd
)

echo [make] starting dashboard on :%UI_PORT%
start /b "" cmd /c "pushd frontend && call npm run dev -- --port %UI_PORT% > ..\%RUN_DIR%\ui.log" 2>&1"
call :wait_ui
if errorlevel 1 goto :fail

echo [make] pipeline complete
echo [make] dashboard: http://localhost:%UI_PORT%   API: http://127.0.0.1:%API_PORT%/health
echo [make] logs in %RUN_DIR%\api.log and %RUN_DIR%\ui.log - stop with make.bat --stop
exit /b 0

:stop
call :stop_quiet
echo [make] stopped
exit /b 0

:stop_quiet
REM kill pids recorded by earlier runs
if exist "%RUN_DIR%\api.pid" (
    for /f %%p in (%RUN_DIR%\api.pid) do taskkill /f /pid %%p >nul 2>&1
    del "%RUN_DIR%\api.pid"
)
if exist "%RUN_DIR%\ui.pid" (
    for /f %%p in (%RUN_DIR%\ui.pid) do taskkill /f /pid %%p >nul 2>&1
    del "%RUN_DIR%\ui.pid"
)
REM also stop anything by window title so --stop works across shell restarts
taskkill /fi "WINDOWTITLE eq AirStat API*" /f >nul 2>&1
taskkill /fi "WINDOWTITLE eq AirStat UI*" /f >nul 2>&1
exit /b 0

:wait_api
for /l %%i in (1,1,30) do (
    curl -sf http://127.0.0.1:%API_PORT%/health >nul 2>&1 && exit /b 0
    timeout /t 1 /nobreak >nul
)
echo [make] API failed to become healthy - check %RUN_DIR%\api.log
exit /b 1

:wait_ui
for /l %%i in (1,1,30) do (
    curl -sf http://localhost:%UI_PORT%/ >nul 2>&1 && exit /b 0
    timeout /t 1 /nobreak >nul
)
echo [make] dashboard failed to start - check %RUN_DIR%\ui.log
exit /b 1

:fail_popd
popd
goto :fail

:fail
echo [make] FAILED - see messages above
exit /b 1
