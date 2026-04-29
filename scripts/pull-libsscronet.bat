@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "DEVICE_ID=4a808af8"
set "USE_SU=1"
if /I "%~1"=="noroot" set "USE_SU=0"

set "DESKTOP=%USERPROFILE%\Desktop"
set "TARGET_FILE=%DESKTOP%\libsscronet_%DEVICE_ID%.so"
set "TMP_DIR=%TEMP%\pull_libsscronet_%RANDOM%%RANDOM%"
set "MATCH_FILE=%TMP_DIR%\matches.txt"
set "ERR_FILE=%TMP_DIR%\find.err"
set "CHECK_FILE=%TMP_DIR%\check.txt"
set "FALLBACK_FILE=%TMP_DIR%\fallback.txt"
set "TEMP_SO=%TMP_DIR%\libsscronet.so"

mkdir "%TMP_DIR%" >nul 2>nul

where adb >nul 2>nul
if errorlevel 1 (
    echo [ERROR] adb.exe not found in PATH.
    goto :cleanup_fail
)

for /f "delims=" %%i in ('adb -s %DEVICE_ID% get-state 2^>nul') do set "DEVICE_STATE=%%i"
if /I not "!DEVICE_STATE!"=="device" (
    echo [ERROR] Device %DEVICE_ID% is not connected or not in device state.
    goto :cleanup_fail
)

echo [INFO] Searching /data/app for entries matching *aweme* ...
if "%USE_SU%"=="1" (
    adb -s %DEVICE_ID% shell su -c "find /data/app -name \"*aweme*\"" 1>"%MATCH_FILE%" 2>"%ERR_FILE%"
) else (
    adb -s %DEVICE_ID% shell "find /data/app -name \"*aweme*\"" 1>"%MATCH_FILE%" 2>"%ERR_FILE%"
)
if errorlevel 1 goto :handle_find_error

set "SOURCE_PATH="
for /f "usebackq delims=" %%i in ("%MATCH_FILE%") do (
    set "REL=%%i"
    if defined REL (
        set "CANDIDATE=!REL!\lib\arm64\libsscronet.so"
        set "CANDIDATE=!CANDIDATE:\=/!"

        if "%USE_SU%"=="1" (
            adb -s %DEVICE_ID% shell su -c "if [ -f '!CANDIDATE!' ]; then echo !CANDIDATE!; fi" 1>"%CHECK_FILE%" 2>nul
        ) else (
            adb -s %DEVICE_ID% shell "if [ -f '!CANDIDATE!' ]; then echo !CANDIDATE!; fi" 1>"%CHECK_FILE%" 2>nul
        )

        for /f "usebackq delims=" %%p in ("%CHECK_FILE%") do (
            echo [INFO] Found candidate: %%p
            if not defined SOURCE_PATH set "SOURCE_PATH=%%p"
        )
    )
)

if not defined SOURCE_PATH (
    echo [INFO] No direct lib/arm64 hit found. Trying fallback search ...
    if "%USE_SU%"=="1" (
        adb -s %DEVICE_ID% shell su -c "find /data/app -path \"*aweme*/lib/arm64/libsscronet.so\"" 1>"%FALLBACK_FILE%" 2>"%ERR_FILE%"
    ) else (
        adb -s %DEVICE_ID% shell "find /data/app -path \"*aweme*/lib/arm64/libsscronet.so\"" 1>"%FALLBACK_FILE%" 2>"%ERR_FILE%"
    )
    if errorlevel 1 goto :handle_find_error

    for /f "usebackq delims=" %%i in ("%FALLBACK_FILE%") do (
        set "REL=%%i"
        if defined REL (
            set "SOURCE_PATH=!REL!"
            echo [INFO] Found candidate: !SOURCE_PATH!
            goto :found_source
        )
    )
)

:found_source
if not defined SOURCE_PATH (
    echo [ERROR] libsscronet.so was not found under any *aweme* path.
    goto :cleanup_fail
)

echo [INFO] Exporting !SOURCE_PATH! to "%TARGET_FILE%" ...
if "%USE_SU%"=="1" (
    adb -s %DEVICE_ID% exec-out su -c "cat '!SOURCE_PATH!'" 1>"%TEMP_SO%" 2>"%ERR_FILE%"
) else (
    adb -s %DEVICE_ID% pull "!SOURCE_PATH!" "%TEMP_SO%" 1>nul 2>"%ERR_FILE%"
)
if errorlevel 1 (
    type "%ERR_FILE%"
    echo [ERROR] Export failed.
    goto :cleanup_fail
)

if not exist "%TEMP_SO%" (
    echo [ERROR] Temporary export file was not created.
    goto :cleanup_fail
)

copy /y "%TEMP_SO%" "%TARGET_FILE%" >nul 2>"%ERR_FILE%"
if errorlevel 1 (
    type "%ERR_FILE%"
    echo [ERROR] Failed to copy the file to the Desktop.
    goto :cleanup_fail
)

if not exist "%TARGET_FILE%" (
    echo [ERROR] Desktop export file was not created.
    goto :cleanup_fail
)

echo [OK] Export completed: "%TARGET_FILE%"
goto :cleanup_ok

:handle_find_error
type "%ERR_FILE%"
findstr /C:"Permission denied" "%ERR_FILE%" >nul
if not errorlevel 1 (
    if "%USE_SU%"=="1" (
        echo [ERROR] Even with su, /data/app is still not readable. Check whether the device is rooted and su works.
    ) else (
        echo [ERROR] The adb shell user cannot read /data/app on this device.
        echo [INFO] This script uses su by default. If you forced non-root mode, run it without arguments.
    )
) else (
    echo [ERROR] Remote search failed.
)
goto :cleanup_fail

:cleanup_ok
if exist "%TMP_DIR%" rd /s /q "%TMP_DIR%" >nul 2>nul
endlocal
exit /b 0

:cleanup_fail
if exist "%TMP_DIR%" rd /s /q "%TMP_DIR%" >nul 2>nul
endlocal
exit /b 1
