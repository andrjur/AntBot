@echo off
SETLOCAL EnableDelayedExpansion

echo #######################################
echo # Cleaning Python cache directories...
echo #######################################

set "count=0"
for /d /r "c:\Trae\AntBot" %%i in (__pycache__) do (
    if exist "%%i" (
        rd /s /q "%%i"
        set /a "count+=1"
        echo Removed: %%i
    )
)

for /d /r "c:\Trae\AntBot" %%i in (.pytest_cache) do (
    if exist "%%i" (
        rd /s /q "%%i"
        set /a "count+=1"
        echo Removed: %%i
    )
)

echo #######################################
echo # Total removed: !count! cache directories
echo #######################################

if !count! == 0 (
    echo No cache directories found to clean
) else (
    echo Cache cleaning completed successfully
)

ENDLOCAL