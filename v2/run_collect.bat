@echo off
setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0"
set "LOG_DIR=%PROJECT_DIR%logs"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

set "LOG_FILE=%LOG_DIR%\collect.log"
set "TIMESTAMP=%DATE% %TIME%"

echo [%TIMESTAMP%] ===== Collect started ===== >> "%LOG_FILE%"

pushd "%PROJECT_DIR%"
python pipeline\pipeline.py --sources github,rss --limit 20 --verbose >> "%LOG_FILE%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

popd

echo [%TIMESTAMP%] ===== Collect finished (exit=%EXIT_CODE%) ===== >> "%LOG_FILE%"

exit /b %EXIT_CODE%
