@echo off
REM ============================================================
REM  3T Reader — Windows build script
REM  Run from repo root:  installer\windows\build_win.bat
REM ============================================================
setlocal EnableDelayedExpansion

set SPEC=installer\windows\3T_Reader_win.spec
set DIST=dist\win
set WORK=build\win

echo [1/3] Building with PyInstaller...
python -m PyInstaller %SPEC% --distpath %DIST% --workpath %WORK% --noconfirm
if errorlevel 1 (
    echo ERROR: PyInstaller failed.
    exit /b 1
)

echo [2/3] Verifying output...
if not exist "%DIST%\3T Reader\3T Reader.exe" (
    echo ERROR: Executable not found.
    exit /b 1
)

echo [3/3] Done.
echo Output: %DIST%\3T Reader\
echo Run:    "%DIST%\3T Reader\3T Reader.exe"
endlocal
