@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
python "%SCRIPT_DIR%check_oci_vm_status.py" --ping %*
echo.
echo Exit code: %ERRORLEVEL%
pause
