@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
python "%SCRIPT_DIR%setup_oci_network.py" %*
echo.
echo Exit code: %ERRORLEVEL%
pause
