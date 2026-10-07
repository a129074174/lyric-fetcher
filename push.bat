@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

rem ============================================================
rem  push.bat - reusable auto commit + push helper
rem
rem  Copy this file into the root folder of any git project.
rem  It always operates on the folder where the script itself
rem  lives, so it does not matter which directory you call it from.
rem
rem  Usage:
rem    push.bat                    -> auto commit message = update
rem    push.bat "your message"     -> custom commit message
rem
rem  Env switches:
rem    NOPAUSE=1                   -> skip the final pause
rem                                  (for scripted / piped use)
rem
rem  NOTE: keep this file pure ASCII. cmd.exe decodes a .bat with the
rem  active code page, so non-ASCII chars here break the parser.
rem  Keep commit messages out of this file; pass them as arguments.
rem ============================================================

cd /d "%~dp0"
echo.
echo [push] repo   : %CD%
echo.

rem ---------- 1. must be a git repository ----------
git rev-parse --git-dir >nul 2>&1
if errorlevel 1 (
  echo [FAILED] not a git repository.
  echo          run:  git init
  goto :fail
)

rem ---------- 2. identity (fallback only, never writes config) ----------

set "GNAME="
set "GMAIL="
for /f "delims=" %%i in ('git config user.name 2^>nul') do set "GNAME=%%i"
for /f "delims=" %%i in ('git config user.email 2^>nul') do set "GMAIL=%%i"
if "!GNAME!"=="" set "GNAME=local"
if "!GMAIL!"=="" set "GMAIL=local@localhost"

rem ---------- 3. remote ----------

set "REMOTE="
for /f "delims=" %%i in ('git remote 2^>nul') do if not defined REMOTE set "REMOTE=%%i"
if "!REMOTE!"=="" (
  echo [FAILED] no git remote configured.
  echo          run:  git remote add origin "URL_HERE"
  goto :fail
)
echo [push] remote : !REMOTE!

rem ---------- 4. branch ----------

set "BRANCH="
for /f "delims=" %%i in ('git symbolic-ref --short HEAD 2^>nul') do set "BRANCH=%%i"
if "!BRANCH!"=="" set "BRANCH=main"
if /i "!BRANCH!"=="HEAD" set "BRANCH=main"
echo [push] branch : !BRANCH!
echo.

rem ---------- 5. stage + commit ----------

git add -A
git diff --cached --quiet
if not errorlevel 1 (
  echo [push] nothing to commit - skipped.
) else (
  set "MSG=%~1"
  if "!MSG!"=="" set "MSG=%*"
  if "!MSG!"=="" set "MSG=update"
  echo [push] message: !MSG!
  git -c user.name="!GNAME!" -c user.email="!GMAIL!" commit -m "!MSG!"
  if errorlevel 1 (
    echo [FAILED] commit failed.
    goto :fail
  )
)

rem ---------- 6. push ----------

git rev-parse --abbrev-ref --symbolic-full-name "@{u}" >nul 2>&1
if errorlevel 1 (
  echo [push] no upstream yet - creating it.
  git push -u !REMOTE! !BRANCH!
) else (
  git push !REMOTE!
)

if errorlevel 1 (
  echo.
  echo [FAILED] push rejected.
  echo          if this is a non-fast-forward, run:
  echo            git pull --rebase
  echo          then run this script again.
  goto :fail
)

echo.
echo [OK] pushed to !REMOTE!/!BRANCH!
git --no-pager log -1 --oneline
echo.
if /i not "%NOPAUSE%"=="1" pause
endlocal
exit /b 0

:fail
echo.
if /i not "%NOPAUSE%"=="1" pause
endlocal
exit /b 1
