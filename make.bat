@echo off
REM AirStat India — one-command pipeline: generate replay data -> seed -> calculate index ->
REM backtest -> start API -> start dashboard. Safe to re-run; idempotent where possible.
REM
REM Usage:
REM   make.bat            full pipeline (regenerates replay data if missing, fresh seed, starts servers)
REM   make.bat --keep     re-seed without dropping tables (keeps existing data)
REM   make.bat --serve    skip pipeline, just start both servers
REM   make.bat --demo     FULL EXPERIENCE: pipeline + servers + sim portal + 1s collector loop
REM   make.bat --schedule scheduled mode: servers + daily 08:00 IST collection cycle (runs one cycle now)
REM   make.bat --stop     stop any AirStat servers started by this script
REM   make.bat --test     run backend tests only
REM   make.bat --fresh-data  force regeneration of the replay dataset
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
if "%API_PORT%"=="" set "API_PORT=8000"
if "%UI_PORT%"=="" set "UI_PORT=5173"
set "RUN_DIR=%TEMP%\airstat"
if not exist "%RUN_DIR%" mkdir "%RUN_DIR%"
set "LOCK=%RUN_DIR%\pipeline.lock"

set "MODE_STOP=0"
set "MODE_TEST=0"
set "MODE_SERVE=0"
set "MODE_SCHEDULE=0"
set "MODE_DEMO=0"
set "MODE_FRESH=0"
set "MODE_KEEP=0"

for %%a in (%*) do (
    if "%%~a"=="--stop" set "MODE_STOP=1"
    if "%%~a"=="--test" set "MODE_TEST=1"
    if "%%~a"=="--serve" set "MODE_SERVE=1"
    if "%%~a"=="--schedule" set "MODE_SCHEDULE=1"
    if "%%~a"=="--demo" set "MODE_DEMO=1"
    if "%%~a"=="--fresh-data" set "MODE_FRESH=1"
    if "%%~a"=="--keep" set "MODE_KEEP=1"
)

if "%MODE_STOP%"=="1" goto :do_stop
if "%MODE_TEST%"=="1" goto :do_test
if "%MODE_SERVE%"=="1" goto :do_serve
if "%MODE_SCHEDULE%"=="1" goto :do_schedule

goto :do_default

:do_stop
call :stop_existing
echo [make] stopped
exit /b 0

:do_test
call :check_env || goto :fail
echo [make] running backend tests
"%PY%" -m pytest backend\tests -q || goto :fail
exit /b 0

:do_serve
call :check_lock || exit /b 1
call :stop_existing
call :start_api || goto :fail
call :start_ui || goto :fail
if "%MODE_DEMO%"=="1" call :start_demo_extra
echo [make] dashboard: http://localhost:%UI_PORT%  ·  API: http://127.0.0.1:%API_PORT%/health
if "%MODE_DEMO%"=="1" goto :log_demo
echo [make] logs in %RUN_DIR%\api.log, ui.log - stop with make.bat --stop
goto :wait_forever

:do_schedule
call :check_lock || exit /b 1
call :stop_existing
call :start_scheduler
call :start_api || goto :fail
call :start_ui || goto :fail
if "%MODE_DEMO%"=="1" call :start_demo_extra
echo [make] scheduled mode: daily collection at 08:00 IST ^(cron equivalent: 0 8 * * *^)
echo [make] dashboard: http://localhost:%UI_PORT%  ·  API: http://127.0.0.1:%API_PORT%/health
if "%MODE_DEMO%"=="1" goto :log_sched_demo
echo [make] logs in %RUN_DIR%\scheduler.log, api.log, ui.log - stop with make.bat --stop
goto :wait_forever

:log_sched_demo
echo [make] logs in %RUN_DIR%\scheduler.log, api.log, ui.log, portal.log, collector.log - stop with make.bat --stop
goto :wait_forever

:do_default
call :check_lock || exit /b 1
call :check_env || goto :fail

REM 2. replay dataset (generate if missing or forced)
if "%MODE_FRESH%"=="1" if exist data\fixtures\replay_quotes.jsonl del data\fixtures\replay_quotes.jsonl
if exist data\fixtures\replay_quotes.jsonl (
    echo [make] replay dataset present - skipping generation ^(use --fresh-data to force^)
) else (
    echo [make] generating replay dataset ^(seed 26056^)
    "%PY%" scripts\generate_replay_data.py || goto :fail
)

REM 3. seed + index + backtest
echo [make] seeding database and running pipeline
"%PY%" scripts\seed.py %* || goto :fail

REM 4. tests
echo [make] running backend tests
"%PY%" -m pytest backend\tests -q || goto :fail

REM 5. servers
call :stop_existing
call :start_api || goto :fail
call :start_ui || goto :fail

REM 6. demo mode: portal + collector loop
if "%MODE_DEMO%"=="1" call :start_demo_extra

echo [make] pipeline complete
echo [make] dashboard: http://localhost:%UI_PORT%  ·  API: http://127.0.0.1:%API_PORT%/health
if "%MODE_DEMO%"=="1" goto :log_demo
echo [make] logs in %RUN_DIR%\api.log, ui.log - stop with make.bat --stop
goto :wait_forever

:log_demo
echo [make] logs in %RUN_DIR%\api.log, ui.log, portal.log, collector.log - stop with make.bat --stop
goto :wait_forever

:start_demo_extra
call :start_portal
call :start_collector 1
exit /b 0

:check_lock
if not exist "%LOCK%" goto :write_lock
for /f "usebackq tokens=*" %%p in ("%LOCK%") do set "LOCK_PID=%%p"
if not defined LOCK_PID goto :write_lock
powershell -NoProfile -Command "if (Get-Process -Id %LOCK_PID% -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 goto :write_lock
echo [make] another make.bat is running ^(pid %LOCK_PID%^) - refusing to start. Stop it with make.bat --stop or kill %LOCK_PID%.
exit /b 1

:write_lock
powershell -NoProfile -Command "Set-Content -Path '%LOCK%' -Value $PID" >nul 2>&1
exit /b 0

:stop_existing
if exist "%LOCK%" del "%LOCK%" >nul 2>&1
if exist "%RUN_DIR%\api.pid" call :kill_pid_file api.pid
if exist "%RUN_DIR%\ui.pid" call :kill_pid_file ui.pid
if exist "%RUN_DIR%\portal.pid" call :kill_pid_file portal.pid
if exist "%RUN_DIR%\collector.pid" call :kill_pid_file collector.pid
if exist "%RUN_DIR%\scheduler.pid" call :kill_pid_file scheduler.pid
powershell -NoProfile -Command "8000,5173 | ForEach-Object { $port = $_; Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | ForEach-Object { if ($_.OwningProcess -gt 0) { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } } }" >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -and ($_.CommandLine -like '*uvicorn backend.app.main:app*' -or $_.CommandLine -like '*serve_sim_portal.py*' -or $_.CommandLine -like '*collect_demo.py*' -or $_.CommandLine -like '*schedule_collect.py*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
exit /b 0

:kill_pid_file
set "PF=%~1"
for /f "usebackq tokens=*" %%p in ("%RUN_DIR%\%PF%") do (
    powershell -NoProfile -Command "Stop-Process -Id %%p -Force -ErrorAction SilentlyContinue" >nul 2>&1
    echo [make] stopped %PF% pid=%%p
)
del "%RUN_DIR%\%PF%" >nul 2>&1
exit /b 0

:check_env
if not exist "%PY%" (
    echo [make] creating Python venv
    python -m venv .venv || exit /b 1
    "%PY%" -m pip install --quiet -r requirements.txt || exit /b 1
) else (
    "%PY%" -c "import apscheduler, fastapi" >nul 2>&1
    if errorlevel 1 (
        echo [make] venv missing dependencies - installing requirements.txt
        "%PY%" -m pip install --quiet -r requirements.txt || exit /b 1
    )
)
exit /b 0

:start_api
echo [make] starting API on :%API_PORT%
powershell -NoProfile -Command "$p = Start-Process -FilePath '%PY%' -WorkingDirectory '%CD%' -ArgumentList @('-m', 'uvicorn', 'backend.app.main:app', '--port', '%API_PORT%') -RedirectStandardOutput '%RUN_DIR%\api.log' -RedirectStandardError '%RUN_DIR%\api_err.log' -PassThru -NoNewWindow; Set-Content -Path '%RUN_DIR%\api.pid' -Value $p.Id" >nul 2>&1
call :wait_api
exit /b %errorlevel%

:wait_api
for /l %%i in (1,1,30) do (
    curl -sf http://127.0.0.1:%API_PORT%/health >nul 2>&1
    if not errorlevel 1 (
        if exist "%RUN_DIR%\api.pid" (
            for /f "usebackq tokens=*" %%p in ("%RUN_DIR%\api.pid") do echo [make] API healthy ^(pid %%p^)
        ) else (
            echo [make] API healthy
        )
        exit /b 0
    )
    powershell -NoProfile -Command "Start-Sleep -Seconds 1" >nul 2>&1
)
echo [make] API failed to become healthy - check %RUN_DIR%\api.log
exit /b 1

:start_ui
if not exist frontend\node_modules (
    echo [make] installing frontend dependencies ^(first run^)
    pushd frontend && call npm install || (popd & exit /b 1)
    popd
)
echo [make] starting dashboard on :%UI_PORT%
powershell -NoProfile -Command "$p = Start-Process -FilePath 'node' -WorkingDirectory '%CD%\frontend' -ArgumentList @('node_modules\vite\bin\vite.js', '--port', '%UI_PORT%', '--host', '127.0.0.1') -RedirectStandardOutput '%RUN_DIR%\ui.log' -RedirectStandardError '%RUN_DIR%\ui_err.log' -PassThru -NoNewWindow; Set-Content -Path '%RUN_DIR%\ui.pid' -Value $p.Id" >nul 2>&1
call :wait_ui
exit /b %errorlevel%

:wait_ui
for /l %%i in (1,1,30) do (
    curl -sf http://127.0.0.1:%UI_PORT%/ >nul 2>&1
    if not errorlevel 1 (
        if exist "%RUN_DIR%\ui.pid" (
            for /f "usebackq tokens=*" %%p in ("%RUN_DIR%\ui.pid") do echo [make] dashboard healthy ^(pid %%p^)
        ) else (
            echo [make] dashboard healthy
        )
        exit /b 0
    )
    powershell -NoProfile -Command "Start-Sleep -Seconds 1" >nul 2>&1
)
echo [make] dashboard failed to start - check %RUN_DIR%\ui.log
exit /b 1

:start_portal
echo [make] starting sim fare portal on :8811 ^(robots.txt-gated scrape target^)
powershell -NoProfile -Command "$p = Start-Process -FilePath '%PY%' -WorkingDirectory '%CD%' -ArgumentList @('scripts\serve_sim_portal.py') -RedirectStandardOutput '%RUN_DIR%\portal.log' -RedirectStandardError '%RUN_DIR%\portal_err.log' -PassThru -NoNewWindow; Set-Content -Path '%RUN_DIR%\portal.pid' -Value $p.Id" >nul 2>&1
call :wait_portal
exit /b %errorlevel%

:wait_portal
for /l %%i in (1,1,20) do (
    curl -sf http://127.0.0.1:8811/robots.txt >nul 2>&1
    if not errorlevel 1 (
        if exist "%RUN_DIR%\portal.pid" (
            for /f "usebackq tokens=*" %%p in ("%RUN_DIR%\portal.pid") do echo [make] portal healthy ^(pid %%p^)
        ) else (
            echo [make] portal healthy
        )
        exit /b 0
    )
    powershell -NoProfile -Command "Start-Sleep -Seconds 1" >nul 2>&1
)
echo [make] portal failed to start - check %RUN_DIR%\portal.log
exit /b 1

:start_collector
set "INTERVAL=%~1"
if "%INTERVAL%"=="" set "INTERVAL=1"
echo [make] starting collector loop: fresh collection every %INTERVAL%s ^(demo retention prunes to 90 virtual days, base period always kept^)
powershell -NoProfile -Command "$p = Start-Process -FilePath '%PY%' -WorkingDirectory '%CD%' -ArgumentList @('scripts\collect_demo.py', '--interval', '%INTERVAL%') -RedirectStandardOutput '%RUN_DIR%\collector.log' -RedirectStandardError '%RUN_DIR%\collector_err.log' -PassThru -NoNewWindow; Set-Content -Path '%RUN_DIR%\collector.pid' -Value $p.Id" >nul 2>&1
if exist "%RUN_DIR%\collector.pid" (
    for /f "usebackq tokens=*" %%p in ("%RUN_DIR%\collector.pid") do echo [make] collector running ^(pid %%p^) - dashboard auto-refreshes every 10s
) else (
    echo [make] collector running - dashboard auto-refreshes every 10s
)
exit /b 0

:start_scheduler
echo [make] starting scheduled daily collection ^(08:00 IST, one cycle now^)
powershell -NoProfile -Command "$p = Start-Process -FilePath '%PY%' -WorkingDirectory '%CD%' -ArgumentList @('scripts\schedule_collect.py', '--once') -RedirectStandardOutput '%RUN_DIR%\scheduler.log' -RedirectStandardError '%RUN_DIR%\scheduler_err.log' -PassThru -NoNewWindow; Set-Content -Path '%RUN_DIR%\scheduler.pid' -Value $p.Id" >nul 2>&1
powershell -NoProfile -Command "Start-Sleep -Seconds 2" >nul 2>&1
if exist "%RUN_DIR%\scheduler.pid" (
    for /f "usebackq tokens=*" %%p in ("%RUN_DIR%\scheduler.pid") do (
        powershell -NoProfile -Command "if (Get-Process -Id %%p -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
        if not errorlevel 1 (
            echo [make] scheduler running ^(pid %%p^)
            exit /b 0
        )
    )
)
echo [make] scheduler exited immediately - check %RUN_DIR%\scheduler.log
exit /b 1

:wait_forever
powershell -NoProfile -Command "while ($true) { Start-Sleep -Seconds 3600 }" >nul 2>&1
exit /b 0

:fail
echo [make] FAILED - see messages above
exit /b 1
