@echo off
chcp 65001 >nul
title NEXUS - Compile EXE
echo ===================================================================
echo   NEXUS v1.0.0 - Standalone Executable Binary Compilation
echo ===================================================================
echo.
echo [*] Cleaning previous build artifacts...
if exist "build" rd /s /q "build"
if exist "dist" rd /s /q "dist"

echo [*] Compiling standalone executable with PyInstaller...
pyinstaller --clean --noconfirm "NEXUS_Steam_Checker_v1.0.0.spec"

if %errorlevel% equ 0 (
    echo.
    echo ===================================================================
    echo   [SUCCESS] Compilation complete!
    echo   Executable is ready at: dist\NEXUS_Steam_Checker_v1.0.0.exe
    echo ===================================================================
) else (
    echo.
    echo [ERROR] PyInstaller compilation failed!
)
pause
