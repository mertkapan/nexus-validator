@echo off
title 104Society Discord Bot
color 0b
echo ===================================================
echo         104Society Discord Bot Baslatiliyor...
echo ===================================================
echo.
cd /d "%~dp0"
python bot_104society.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [UYARI] Bot kapandi veya bir hata olustu.
    pause
)
