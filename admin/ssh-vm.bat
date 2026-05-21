@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
if "%~1"=="" (
    echo Usage: ssh-vm.bat ^<vm-name^> [-- command]
    echo   e.g.: ssh-vm.bat management
    echo   e.g.: ssh-vm.bat worker
    echo   e.g.: ssh-vm.bat worker -- uptime
    echo.
    echo VMs: management, worker, laboratory
    if not defined PROMPT pause
    exit /b 1
)
python "%SCRIPT_DIR%ssh_vm.py" %*
if errorlevel 1 (
    if not defined PROMPT pause
)
