@echo off
setlocal
chcp 65001 >nul 2>&1

rem ============================================================
rem  test.bat - run the unittest suite from the repo root
rem
rem  Usage:
rem    test.bat                   run every test_*.py under tests\
rem    test.bat test_textutil.py  run only that file
rem
rem  Why this exists: running "python tests\test_xxx.py" directly
rem  fails with ModuleNotFoundError, because Python then puts the
rem  tests\ folder - not the repo root - on sys.path. Going through
rem  "python -m unittest" from the repo root keeps the root on
rem  sys.path, so "import fetcher" resolves.
rem
rem  NOTE: keep this file pure ASCII. cmd.exe decodes a .bat with
rem  the active code page, so non-ASCII here breaks the parser.
rem ============================================================

cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo [FAILED] .venv\Scripts\python.exe not found.
  echo          run setup.bat first.
  goto :fail
)

set "PAT=test_*.py"
if not "%~1"=="" set "PAT=%~1"

echo [test] repo    : %CD%
echo [test] pattern : %PAT%
echo.

"%PY%" -m unittest discover -s tests -p "%PAT%" -v
set "RC=%errorlevel%"

echo.
if "%RC%"=="0" (
  echo [OK] all tests passed.
) else (
  echo [FAILED] exit code %RC% - some tests failed, see output above.
)

if /i not "%NOPAUSE%"=="1" pause
endlocal & exit /b %RC%

:fail
echo.
if /i not "%NOPAUSE%"=="1" pause
endlocal & exit /b 1
