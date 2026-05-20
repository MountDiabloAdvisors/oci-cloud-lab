@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
python "%SCRIPT_DIR%oci_launch_until_available.py" --profile "%SCRIPT_DIR%profiles\management.json" %*
echo.
echo Exit code: %ERRORLEVEL%
pause
