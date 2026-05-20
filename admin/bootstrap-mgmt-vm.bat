@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
python "%SCRIPT_DIR%bootstrap_mgmt_vm.py" %*
echo.
echo Exit code: %ERRORLEVEL%
pause
