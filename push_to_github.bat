@echo off
chcp 65001 >nul
title NEXUS - Push to GitHub Cloud

echo ===================================================================
echo   NEXUS v1.0.0 - GitHub Cloud Synchronization
echo ===================================================================
echo.

where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Git is not installed or not in PATH!
    echo Please install Git from https://git-scm.com/
    pause
    exit /b 1
)

if not exist ".git" (
    echo [*] Initializing local Git repository...
    git init
    git branch -M main
)

echo [*] Staging files...
git add .

echo [*] Committing updates...
git commit -m "NEXUS Platform Authentication State Validator - Cloud Runner & Discord Sink"

echo.
git remote get-url origin >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] No remote repository linked yet.
    set /p REPO_URL="Enter your GitHub Repository URL (e.g. https://github.com/username/repo.git): "
    if not "%REPO_URL%"=="" (
        git remote add origin %REPO_URL%
    ) else (
        echo [ERROR] No URL provided.
        pause
        exit /b 1
    )
)

echo [*] Pushing updates to GitHub (main branch)...
git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo ===================================================================
    echo   [SUCCESS] Code successfully pushed to GitHub!
    echo   You can now run it 24/7 via GitHub Actions without a VDS!
    echo ===================================================================
) else (
    echo.
    echo [!] Push failed. Ensure you are authenticated with GitHub and the repository exists.
)

echo.
pause
