@echo off
setlocal
chcp 65001 >nul 2>nul
cd /d "%~dp0"

echo ==========================================================
echo   lyric-fetcher  -  environment setup
echo ==========================================================
echo.

rem ---------- locate uv ----------
set "UV="
where uv >nul 2>nul
if not errorlevel 1 set "UV=uv"
if not defined UV if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV=%USERPROFILE%\.local\bin\uv.exe"
if not defined UV (
    echo [ERROR] uv not found.
    echo         Install it with:  winget install --id astral-sh.uv -e
    echo         Then close this window and run setup.bat again.
    goto :fail
)
echo [0/5] uv  : %UV%

set "HAS_GIT=0"
where git >nul 2>nul
if not errorlevel 1 set "HAS_GIT=1"
if "%HAS_GIT%"=="1" (
    echo       git : found
) else (
    echo       git : NOT FOUND - version control will be skipped
)

rem ---------- git identity fallback ----------
set "GITID="
if "%HAS_GIT%"=="1" (
    git config --get user.name >nul 2>nul
    if errorlevel 1 set "GITID=-c user.name=lyric-fetcher -c user.email=lyric-fetcher@localhost"
)

echo.
echo [1/5] Installing Python 3.12 ...
"%UV%" python install 3.12
if errorlevel 1 goto :fail

echo.
echo [2/5] Creating virtual environment ...
if exist ".venv\Scripts\python.exe" (
    echo       .venv already exists - skipping
) else (
    "%UV%" venv --python 3.12
    if errorlevel 1 goto :fail
)

echo.
echo [3/5] Installing dependencies ...
"%UV%" pip install -r requirements.txt
if errorlevel 1 goto :fail

echo.
echo [4/5] Running self-check ...
".venv\Scripts\python.exe" tools\check_env.py
if errorlevel 1 goto :fail

echo.
echo [5/5] Initializing git repository ...
if "%HAS_GIT%"=="0" goto :git_skip
if exist ".git" (
    echo       .git already exists - staging current state
    git add -A
    git %GITID% commit -q -m "chore: sync workspace" >nul 2>nul
    goto :git_done
)
git init -q
if errorlevel 1 goto :fail
git add -A
if errorlevel 1 goto :fail
git %GITID% commit -q -m "chore(step1): project skeleton, deps and git setup"
if errorlevel 1 goto :fail
echo       repository created, first commit done
goto :git_done

:git_skip
echo       skipped - git not available

:git_done
echo.
echo ==========================================================
echo   DONE - environment is ready
echo ==========================================================
echo.
echo Verify with:
echo   uv run python -m fetcher --version
echo   uv run python -m fetcher search
echo.
pause
endlocal
exit /b 0

:fail
echo.
echo [FAILED] setup aborted - see the message above.
echo.
pause
endlocal
exit /b 1
