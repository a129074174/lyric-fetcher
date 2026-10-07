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

rem ---------- 3. remote (optional - we still commit locally) ----------

set "REMOTE="
for /f "delims=" %%i in ('git remote 2^>nul') do if not defined REMOTE set "REMOTE=%%i"
if "!REMOTE!"=="" (
  echo [push] remote : ^(none^) - local commit only
) else (
  echo [push] remote : !REMOTE!
)

rem ---------- 3b. remote URL sanity check ----------
rem A bare "owner/repo" (as shown on the GitHub web page) is NOT a valid
rem repository URL - git reads it as a local path and push always fails.
rem Detect that shape and upgrade it to a real URL automatically.

set "RURL="
for /f "delims=" %%i in ('git config --get remote.!REMOTE!.url 2^>nul') do set "RURL=%%i"

if not defined RURL goto :url_ok

echo !RURL! | findstr /c:"/" >nul
if errorlevel 1 goto :url_ok
echo !RURL! | findstr /c:"://" >nul
if not errorlevel 1 goto :url_ok
echo !RURL! | findstr /c:"@" >nul
if not errorlevel 1 goto :url_ok
echo !RURL! | findstr /c:":" >nul
if not errorlevel 1 goto :url_ok
if "!RURL:~0,1!"=="." goto :url_ok
if "!RURL:~0,1!"=="/" goto :url_ok

echo [push] WARNING: "!RURL!" is not a usable repository URL -
echo [push]          git reads it as a local path, so push would always fail.
set "RURL=https://github.com/!RURL!.git"
git remote set-url !REMOTE! "!RURL!"
echo [push]          auto-fixed to: !RURL!

:url_ok

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

rem ---------- 6. push (skipped when no remote is configured) ----------

if "!REMOTE!"=="" (
  echo.
  echo [WARN] no git remote configured - committed locally, nothing pushed.
  echo        to enable push later, run:
  echo          git remote add origin "URL_HERE"
  echo.
  echo [OK] local commit:
  git --no-pager log -1 --oneline
  goto :finish
)

git rev-parse --abbrev-ref --symbolic-full-name "@{u}" >nul 2>&1
if errorlevel 1 (
  echo [push] no upstream yet - creating it.
  git push -u !REMOTE! !BRANCH!
) else (
  git push !REMOTE!
)

if errorlevel 1 (
  echo.
  echo [FAILED] push rejected. usual causes:
  echo   1^) remote URL is wrong   -^> check:  git remote -v
  echo   2^) authentication needed  -^> GitHub wants a token, not your password
  echo   3^) remote is ahead        -^> run:   git pull --rebase
  echo   then run this script again.
  goto :fail
)

echo.
echo [OK] pushed to !REMOTE!/!BRANCH!
git --no-pager log -1 --oneline

:finish
echo.
if /i not "%NOPAUSE%"=="1" pause
endlocal
exit /b 0

:fail
echo.
if /i not "%NOPAUSE%"=="1" pause
endlocal
exit /b 1
