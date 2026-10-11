@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv" (
    echo [setup] creating virtual environment...
    uv venv --python 3.12
    uv pip install -r requirements.txt
)

uv run python -m fetcher %*

if errorlevel 1 (
    echo [warn] fetcher exited with code %errorlevel%
)
